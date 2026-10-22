import re
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
from typing import List
from bson import ObjectId

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: Literal["developer", "salesperson"]
    # Must be true: the person is 18 or older and accepts the Terms and Privacy Policy.
    accepted_terms: bool

    @field_validator("accepted_terms")
    @classmethod
    def must_accept_terms(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must agree to the Terms of Service and Privacy Policy to sign up")
        return value

    # Optional role-specific fields
    skills: Optional[list[str]] = None          # developer
    company_name: Optional[str] = None          # salesperson


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    created_at: datetime
    email_verified: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ProjectCreate(BaseModel):
    title: str = Field(min_length=10, max_length=200)
    description: str = Field(min_length=30, max_length=3000)
    category: str
    budget: float = Field(gt=0)
    # Ignored by the server: every project is created in the platform currency.
    currency: str = "KES"
    deadline: datetime
    client_name: str
    client_email: EmailStr
    tags: Optional[List[str]] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    budget: Optional[float] = None
    status: Optional[Literal["open", "in_progress", "completed", "cancelled"]] = None
    deadline: Optional[datetime] = None


class ApplicationCreate(BaseModel):
    proposed_budget: Optional[float] = None
    cover_letter: str = Field(min_length=10, max_length=2000)


class ProjectResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str
    budget: float
    currency: str
    status: str
    deadline: datetime
    salesperson_id: str
    assigned_to: Optional[str] = None
    applications_count: int
    created_at: datetime

class MessageCreate(BaseModel):
    receiver_id: str
    project_id: str
    content: str = Field(min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_name: str
    content: str
    is_read: bool
    created_at: datetime

class PaymentInitialize(BaseModel):
    project_id: str
    # Optional: the amount is always the project's agreed price. If a client
    # sends one anyway it must match, so a stale screen cannot charge a wrong sum.
    amount: Optional[float] = Field(None, gt=0)


class PriceProposalCreate(BaseModel):
    amount: float = Field(gt=0)
    reason: str = Field(min_length=10, max_length=500)


class PriceProposalDecision(BaseModel):
    approve: bool
    note: Optional[str] = Field(None, max_length=500)


class ProblemReport(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class PaymentVerify(BaseModel):
    reference: str

class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = None
    skills: Optional[List[str]] = None          # developer only
    company_name: Optional[str] = None          # salesperson only


class UserProfileResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    phone: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    wallet_balance: float
    total_earned: float
    created_at: datetime


class WalletResponse(BaseModel):
    wallet_balance: float
    total_earned: float
    currency: str = "KES"


class PayoutAccountAdd(BaseModel):
    """M-Pesa number that withdrawals are paid to."""
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def normalise_kenyan_number(cls, value: str) -> str:
        # Accepts 0712345678, 712345678, 254712345678 and +254712345678
        # (also 01xx numbers) and stores it as 0712345678.
        digits = re.sub(r"[\s\-()]", "", value)
        match = re.fullmatch(r"(?:\+?254|0)?([71]\d{8})", digits)
        if not match:
            raise ValueError("Enter a valid Kenyan mobile number, e.g. 0712345678")
        return "0" + match.group(1)


class WithdrawRequest(BaseModel):
    amount: float = Field(gt=0)

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

class ReviewCreate(BaseModel):
    project_id: str
    reviewed_user_id: str
    rating: float = Field(ge=1, le=5)
    comment: str = Field(min_length=10, max_length=1000)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)