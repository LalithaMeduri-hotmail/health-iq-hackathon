"""Patient display name for the documents a clinician signs.

A reviewed medicine plan is unusable at a pharmacy or another clinic without a name on it, so
this is the one place the account's display name is read for rendering. Nothing else about the
account leaves this module.
"""

from app.repositories import cosmos_repo

# Demo flows run without a registered account; the document still needs a subject line.
_FALLBACK = "Health IQ user"


async def display_name(user_id: str) -> str:
    """Best available human name for `user_id`, never an identifier the patient did not choose."""
    account = await cosmos_repo.get_account(user_id)
    if account is None:
        return _FALLBACK
    return account.get("displayName") or account.get("username") or _FALLBACK
