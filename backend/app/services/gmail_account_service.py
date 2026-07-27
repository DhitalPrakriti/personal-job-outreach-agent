"""Connected Gmail account storage and token handling."""

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import GmailAccountModel


@dataclass(frozen=True)
class GmailAccountCredentials:
    email: str
    refresh_token: str


class GmailAccountService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def list_accounts(self) -> list[GmailAccountModel]:
        await self.import_env_account_if_needed()
        result = await self.session.execute(select(GmailAccountModel).order_by(GmailAccountModel.email))
        return list(result.scalars().all())

    async def get_default_credentials(self, *, require_reply_sync: bool = False) -> GmailAccountCredentials | None:
        await self.import_env_account_if_needed()
        query = select(GmailAccountModel).where(GmailAccountModel.status == "connected")
        if require_reply_sync:
            query = query.where(GmailAccountModel.reply_sync_enabled.is_(True))
        else:
            query = query.where(GmailAccountModel.send_enabled.is_(True))
        result = await self.session.execute(
            query.order_by(GmailAccountModel.is_default.desc(), GmailAccountModel.created_at)
        )
        account = self.select_effective_account(
            list(result.scalars().all()),
            require_reply_sync=require_reply_sync,
            require_send=not require_reply_sync,
        )
        if account:
            return GmailAccountCredentials(
                email=account.email,
                refresh_token=self._decrypt(account.encrypted_refresh_token),
            )
        fallback_email = (self.settings.google_sender_email or "").lower().strip()
        preferred_email = self.preferred_email
        fallback_is_allowed = not preferred_email or fallback_email == preferred_email
        if self.settings.google_refresh_token and fallback_email and fallback_is_allowed:
            return GmailAccountCredentials(
                email=fallback_email,
                refresh_token=self.settings.google_refresh_token,
            )
        return None

    @property
    def preferred_email(self) -> str:
        return (self.settings.app_allowed_email or self.settings.google_sender_email or "").lower().strip()

    def select_effective_account(
        self,
        accounts: list[GmailAccountModel],
        *,
        require_reply_sync: bool = False,
        require_send: bool = False,
    ) -> GmailAccountModel | None:
        eligible = [account for account in accounts if account.status == "connected"]
        if require_reply_sync:
            eligible = [account for account in eligible if account.reply_sync_enabled]
        if require_send:
            eligible = [account for account in eligible if account.send_enabled]
        if not eligible:
            return None

        preferred_email = self.preferred_email
        if preferred_email:
            preferred = next((account for account in eligible if account.email == preferred_email), None)
            return preferred

        return next((account for account in eligible if account.is_default), eligible[0])

    async def import_env_account_if_needed(self) -> GmailAccountModel | None:
        if not (self.settings.google_refresh_token and self.settings.google_sender_email):
            return None
        normalized_email = self.settings.google_sender_email.lower().strip()
        existing_accounts = await self._accounts_for_email(normalized_email)
        existing = self._canonical_account(existing_accounts)
        if existing:
            changed = False
            changed = await self._disable_duplicate_accounts(existing, existing_accounts) or changed
            if normalized_email == self.preferred_email:
                existing.scopes = "\n".join([
                    "https://www.googleapis.com/auth/gmail.send",
                    "https://www.googleapis.com/auth/gmail.readonly",
                ])
                existing.send_enabled = True
                existing.reply_sync_enabled = True
                existing.status = "connected"
                existing.last_connected_at = datetime.now(UTC)
            if normalized_email == self.preferred_email and not existing.is_default:
                await self.session.execute(update(GmailAccountModel).values(is_default=False))
                existing.is_default = True
                changed = True
            if changed:
                await self.session.commit()
                await self.session.refresh(existing)
            return existing
        has_existing_accounts = bool((await self.session.execute(select(GmailAccountModel.id))).scalar_one_or_none())
        is_default = not has_existing_accounts or normalized_email == self.preferred_email
        if is_default:
            await self.session.execute(update(GmailAccountModel).values(is_default=False))
        account = GmailAccountModel(
            email=normalized_email,
            display_name=normalized_email,
            purpose=self._purpose_for_email(normalized_email),
            encrypted_refresh_token=self._encrypt(self.settings.google_refresh_token),
            scopes="\n".join([
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.readonly",
            ]),
            is_default=is_default,
            send_enabled=True,
            reply_sync_enabled=True,
            status="connected",
            last_connected_at=datetime.now(UTC),
        )
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def upsert_connected_account(
        self,
        *,
        email: str,
        refresh_token: str,
        scopes: list[str],
        display_name: str | None = None,
        purpose: str | None = None,
        make_default: bool | None = None,
    ) -> GmailAccountModel:
        normalized_email = email.lower().strip()
        existing_accounts = await self._accounts_for_email(normalized_email)
        account = self._canonical_account(existing_accounts)
        has_existing_accounts = bool((await self.session.execute(select(GmailAccountModel.id))).scalar_one_or_none())
        should_default = make_default if make_default is not None else not has_existing_accounts
        if should_default:
            await self.session.execute(update(GmailAccountModel).values(is_default=False))
        if account is None:
            account = GmailAccountModel(email=normalized_email, encrypted_refresh_token=self._encrypt(refresh_token))
            self.session.add(account)
        else:
            await self._disable_duplicate_accounts(account, existing_accounts)
        account.display_name = display_name
        account.purpose = purpose or self._purpose_for_email(normalized_email)
        account.encrypted_refresh_token = self._encrypt(refresh_token)
        account.scopes = "\n".join(scopes)
        account.is_default = should_default or account.is_default
        account.send_enabled = True
        account.reply_sync_enabled = True
        account.status = "connected"
        account.last_connected_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def _accounts_for_email(self, email: str) -> list[GmailAccountModel]:
        result = await self.session.execute(
            select(GmailAccountModel)
            .where(GmailAccountModel.email == email)
            .order_by(
                GmailAccountModel.is_default.desc(),
                GmailAccountModel.last_connected_at.desc().nullslast(),
                GmailAccountModel.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    def _canonical_account(self, accounts: list[GmailAccountModel]) -> GmailAccountModel | None:
        return accounts[0] if accounts else None

    async def _disable_duplicate_accounts(
        self,
        canonical: GmailAccountModel,
        accounts: list[GmailAccountModel],
    ) -> bool:
        changed = False
        for account in accounts:
            if account.id == canonical.id:
                continue
            account.is_default = False
            account.send_enabled = False
            account.reply_sync_enabled = False
            account.status = "duplicate"
            changed = True
        return changed

    async def set_default(self, account_id: UUID) -> GmailAccountModel | None:
        account = await self.session.get(GmailAccountModel, account_id)
        if account is None:
            return None
        await self.session.execute(update(GmailAccountModel).values(is_default=False))
        account.is_default = True
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def update_account(self, account_id: UUID, **updates: object) -> GmailAccountModel | None:
        account = await self.session.get(GmailAccountModel, account_id)
        if account is None:
            return None
        for field in ("purpose", "send_enabled", "reply_sync_enabled", "status"):
            if field in updates and updates[field] is not None:
                setattr(account, field, updates[field])
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def delete_account(self, account_id: UUID) -> GmailAccountModel | None:
        account = await self.session.get(GmailAccountModel, account_id)
        if account is None:
            return None
        if account.email == self.preferred_email:
            raise ValueError("The preferred job-search Gmail account cannot be disconnected.")
        await self.session.delete(account)
        await self.session.commit()
        return account

    def _fernet(self) -> Fernet:
        raw_key = (
            self.settings.gmail_token_encryption_key
            or self.settings.app_auth_secret_key
            or self.settings.automation_api_key
            or "local-development-token-key"
        )
        if raw_key.startswith("gAAAA"):
            # This is probably an encrypted token accidentally supplied as a key; derive instead.
            raw_key = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            return Fernet(raw_key.encode())
        except Exception:
            digest = hashlib.sha256(raw_key.encode()).digest()
            return Fernet(base64.urlsafe_b64encode(digest))

    def _encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        return self._fernet().decrypt(value.encode()).decode()

    def _purpose_for_email(self, email: str) -> str:
        if email == (self.settings.google_sender_email or "").lower() and "outreach" in email:
            return "testing"
        if email == (self.settings.app_allowed_email or "").lower():
            return "job_search"
        return "job_search"
