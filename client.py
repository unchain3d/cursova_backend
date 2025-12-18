from datetime import datetime, timedelta, date, time, timezone
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, field_validator
from models import (
    Users, Trainers, Subscriptions, Sessions, VisitHistory,
    SubscriptionPurchases,
    UserRole, SubscriptionType
)
from dependencies import db_dependency
from auth import get_user

router = APIRouter(
    prefix='/client',
    tags=['client']
)

user_dependency = Annotated[dict, Depends(get_user)]


def generate_time_slots(start_hour: int = 9, end_hour: int = 21) -> List[str]:
    """
    Генерує список доступних слотів
    """
    slots = []
    for hour in range(start_hour, end_hour):
        for minute in [0, 15, 30, 45]:
            time_str = f"{hour:02d}:{minute:02d}"
            slots.append(time_str)
    return slots


class TrainerResponse(BaseModel):
    id: int
    name: str
    specialization: str
    photo_url: Optional[str]
    rating: float

    class Config:
        from_attributes = True


class TrainerDetailResponse(BaseModel):
    id: int
    name: str
    specialization: str
    photo_url: Optional[str]
    rating: float
    description: Optional[str]

    class Config:
        from_attributes = True


class SessionRequest(BaseModel):
    trainer_id: int
    session_time: datetime

    @field_validator('session_time')
    @classmethod
    def validate_session_time(cls, v: datetime):
        if v.minute % 15 != 0:
            raise ValueError("Час має бути кратним 15 хвилинам (наприклад: 12:00, 12:15, 12:30, 15:45)")
        if v.second != 0 or v.microsecond != 0:
            minutes = (v.minute // 15) * 15
            v = v.replace(minute=minutes, second=0, microsecond=0)
        return v


class SubscriptionResponse(BaseModel):
    id: int
    name: str
    subscription_type: str
    price: float
    duration_days: int

    class Config:
        from_attributes = True


class PurchaseRequest(BaseModel):
    subscription_id: int


class ProfileResponse(BaseModel):
    username: str
    email: str
    subscription_type: Optional[str]
    subscription_expires_at: Optional[datetime]
    subscription_active: bool
    visit_history: List[dict]


class BookingResponse(BaseModel):
    id: int
    trainer_id: int
    trainer_name: str
    session_time: datetime
    status: str


class BookingListItem(BaseModel):
    id: int
    trainer_id: int
    trainer_name: str
    session_time: datetime
    status: str

    class Config:
        from_attributes = True


class TimeSlotResponse(BaseModel):
    time: str
    datetime: datetime
    available: bool


@router.get("/trainers", response_model=List[TrainerResponse])
async def get_trainers(db: db_dependency, user: user_dependency):
    """
    Отримати список всіх тренерів
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )
    
    trainers = db.query(Trainers).all()
    return trainers


@router.get("/trainers/{trainer_id}", response_model=TrainerDetailResponse)
async def get_trainer_details(trainer_id: int, db: db_dependency, user: user_dependency):
    """
    Отримати детальну інформацію про тренера
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )
    
    trainer = db.query(Trainers).filter(Trainers.id == trainer_id).first()
    if not trainer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тренер не знайдений"
        )
    
    return trainer


@router.get("/trainers/{trainer_id}/available-slots", response_model=List[TimeSlotResponse])
async def get_available_slots(
        trainer_id: int,
        date: str = Query(..., description="Дата у форматі YYYY-MM-DD"),
        db: db_dependency = None,
        user: user_dependency = None
):
    """
    Отримати список доступних слотів часу для тренера на конкретну дату
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )

    trainer = db.query(Trainers).filter(Trainers.id == trainer_id).first()
    if not trainer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тренер не знайдений"
        )

    try:
        selected_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невірний формат дати. Використовуйте YYYY-MM-DD"
        )

    today = datetime.now(timezone.utc).date()
    if selected_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не можна вибрати дату в минулому"
        )

    time_slots = generate_time_slots()

    start_of_day = datetime.combine(selected_date, time.min)
    end_of_day = datetime.combine(selected_date, time.max)

    booked_sessions = db.query(Sessions).filter(
        Sessions.trainer_id == trainer_id,
        Sessions.session_time >= start_of_day,
        Sessions.session_time < end_of_day + timedelta(days=1),
        Sessions.status == "booked"  # Враховуємо тільки активні бронювання
    ).all()

    booked_times = set()
    for session in booked_sessions:
        if isinstance(session.session_time, datetime):
            session_time = session.session_time.time()
        else:
            session_time = session.session_time
        time_str = f"{session_time.hour:02d}:{session_time.minute:02d}"
        booked_times.add(time_str)

    now = datetime.now(timezone.utc)
    available_slots = []

    for time_str in time_slots:
        hour, minute = map(int, time_str.split(':'))
        slot_datetime = datetime.combine(selected_date, time(hour, minute))
        slot_datetime = slot_datetime.replace(tzinfo=timezone.utc)

        is_booked = time_str in booked_times
        is_past = slot_datetime < now

        available_slots.append(TimeSlotResponse(
            time=time_str,
            datetime=slot_datetime,
            available=not is_booked and not is_past
        ))

    return available_slots


@router.post("/book-session", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def book_session(
        session_request: SessionRequest,
        db: db_dependency,
        user: user_dependency
):
    """
    Записатись на заняття. Перевіряє наявність активного абонемента.
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )

    trainer = db.query(Trainers).filter(Trainers.id == session_request.trainer_id).first()
    if not trainer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тренер не знайдений"
        )

    db_user = db.query(Users).filter(Users.id == user['id']).first()

    if not db_user.subscription_active or not db_user.subscription_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У вас немає активного абонемента. Придбайте абонемент для запису на заняття."
        )

    now_utc = datetime.now(timezone.utc)

    expires_at_utc = db_user.subscription_expires_at
    if expires_at_utc.tzinfo is None:
        expires_at_utc = expires_at_utc.replace(tzinfo=timezone.utc)
    else:
        expires_at_utc = expires_at_utc.astimezone(timezone.utc)

    if expires_at_utc < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ваш абонемент закінчився. Придбайте новий абонемент."
        )

    session_time_utc = session_request.session_time
    if session_time_utc.tzinfo is None:
        session_time_utc = session_time_utc.replace(tzinfo=timezone.utc)
    else:
        session_time_utc = session_time_utc.astimezone(timezone.utc)

    if session_time_utc < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не можна записатись на час в минулому"
        )

    if session_request.session_time.minute % 15 != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Час має бути кратним 15 хвилинам (наприклад: 12:00, 12:15, 12:30, 15:45)"
        )

    slot_start_naive = session_time_utc.replace(tzinfo=None)
    slot_end_naive = (session_time_utc + timedelta(minutes=15)).replace(tzinfo=None)

    conflicting_session = db.query(Sessions).filter(
        Sessions.trainer_id == session_request.trainer_id,
        Sessions.session_time >= slot_start_naive,
        Sessions.session_time < slot_end_naive,
        Sessions.status == "booked"
    ).first()

    if conflicting_session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Цей час вже зайнятий. Оберіть інший час."
        )

    session_time_to_save = session_time_utc
    if session_time_to_save.tzinfo:
        session_time_to_save = session_time_to_save.replace(tzinfo=None)

    new_session = Sessions(
        trainer_id=session_request.trainer_id,
        client_id=user['id'],
        session_time=session_time_to_save,
        status="booked"
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return {
        "id": new_session.id,
        "trainer_id": new_session.trainer_id,
        "trainer_name": trainer.name,
        "session_time": new_session.session_time,
        "status": new_session.status
    }


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def get_subscriptions(db: db_dependency, user: user_dependency):
    """
    Отримати список доступних абонементів
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )
    
    subscriptions = db.query(Subscriptions).all()
    return subscriptions


@router.post("/purchase-subscription", status_code=status.HTTP_200_OK)
async def purchase_subscription(
    purchase_request: PurchaseRequest,
    db: db_dependency,
    user: user_dependency
):
    """
    Придбати абонемент
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )
    
    subscription = db.query(Subscriptions).filter(
        Subscriptions.id == purchase_request.subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Абонемент не знайдений"
        )
    
    db_user = db.query(Users).filter(Users.id == user['id']).first()
    
    now_utc = datetime.now(timezone.utc)
    
    if db_user.subscription_active and db_user.subscription_expires_at:
        expires_at_utc = db_user.subscription_expires_at
        if expires_at_utc.tzinfo is None:
            expires_at_utc = expires_at_utc.replace(tzinfo=timezone.utc)
        else:
            expires_at_utc = expires_at_utc.astimezone(timezone.utc)
            
        if expires_at_utc > now_utc:
            new_expires_at = expires_at_utc + timedelta(days=subscription.duration_days)
        else:
            new_expires_at = now_utc + timedelta(days=subscription.duration_days)
    else:
        new_expires_at = now_utc + timedelta(days=subscription.duration_days)
    
    db_user.subscription_expires_at = new_expires_at.replace(tzinfo=None)
    
    db_user.subscription_type = subscription.subscription_type
    db_user.subscription_active = True

    purchase = SubscriptionPurchases(
        user_id=user['id'],
        subscription_id=subscription.id,
        price=subscription.price,
        purchased_at=now_utc.replace(tzinfo=None)
    )
    db.add(purchase)
    
    db.commit()
    db.refresh(db_user)
    
    return {
        "message": "Абонемент успішно придбано",
        "subscription_type": db_user.subscription_type,
        "expires_at": db_user.subscription_expires_at
    }


@router.get("/sessions", response_model=List[BookingListItem])
async def get_my_sessions(db: db_dependency, user: user_dependency):
    """
    Отримати всі бронювання (sessions) поточного користувача.
    """
    if user["role"] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів",
        )

    sessions = (
        db.query(Sessions)
        .filter(Sessions.client_id == user["id"])
        .order_by(Sessions.session_time.desc())
        .all()
    )

    result: List[BookingListItem] = []
    for s in sessions:
        trainer = db.query(Trainers).filter(Trainers.id == s.trainer_id).first()
        result.append(
            BookingListItem(
                id=s.id,
                trainer_id=s.trainer_id,
                trainer_name=trainer.name if trainer else "Невідомий тренер",
                session_time=s.session_time,
                status=s.status,
            )
        )

    return result


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(db: db_dependency, user: user_dependency):
    """
    Отримати профіль користувача з історією відвідувань
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )

    db_user = db.query(Users).filter(Users.id == user['id']).first()

    visits = db.query(VisitHistory).filter(VisitHistory.user_id == user['id']).order_by(
        VisitHistory.visit_date.desc()
    ).all()

    visit_history = [
        {
            "id": visit.id,
            "trainer_name": visit.trainer_name,
            "visit_date": visit.visit_date
        }
        for visit in visits
    ]

    return {
        "username": db_user.username,
        "email": db_user.email,
        "subscription_type": db_user.subscription_type,
        "subscription_expires_at": db_user.subscription_expires_at,
        "subscription_active": db_user.subscription_active,
        "visit_history": visit_history
    }


@router.post("/complete-session/{session_id}")
async def complete_session(session_id: int, db: db_dependency, user: user_dependency):
    """
    Завершити сесію та додати до історії відвідувань
    """
    if user['role'] != UserRole.CLIENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ тільки для клієнтів"
        )

    session = db.query(Sessions).filter(
        Sessions.id == session_id,
        Sessions.client_id == user['id']
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сесія не знайдена"
        )

    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сесія вже завершена"
        )

    session.status = "completed"

    trainer = db.query(Trainers).filter(Trainers.id == session.trainer_id).first()
    visit = VisitHistory(
        user_id=user['id'],
        trainer_id=session.trainer_id,
        session_id=session.id,
        trainer_name=trainer.name if trainer else "Невідомий тренер",
        visit_date=datetime.now(timezone.utc)
    )

    db.add(visit)
    db.commit()

    return {
        "message": "Сесія успішно завершена",
        "session_id": session.id,
        "visit_added": True
    }


