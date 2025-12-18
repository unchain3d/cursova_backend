"""
Скрипт для заповнення початкових даних: тренерів та абонементів
"""
from database import SessionLocal, engine
import models
from models import Users, UserRole, Trainers, Subscriptions, SubscriptionType
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed_data():
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    
    try:
        admin = db.query(Users).filter(Users.role == UserRole.ADMIN.value).first()
        if not admin:
            admin = Users(
                username="admin",
                email="admin@example.com",
                hashed_password=pwd_context.hash("Admin1234"),
                role=UserRole.ADMIN.value,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print("Створено адміністратора: admin / Admin1234")
        else:
            print("ℹАдміністратор вже існує")

        existing_trainers = db.query(Trainers).count()
        existing_subscriptions = db.query(Subscriptions).count()
        
        if existing_trainers > 0 or existing_subscriptions > 0:
            print("Дані вже існують. Пропускаємо заповнення.")
            return
        
        trainers = [
            Trainers(
                name="Олександр Петренко",
                specialization="Йога",
                photo_url="https://i.pinimg.com/736x/48/84/70/488470220cdbdd72f73405d473a2e8f6.jpg",
                rating=4.3,
                description="Досвідчений інструктор з йоги з 10-річним стажем. Спеціалізується на хатха-йозі та він'ясі.",
                experience_years=10,
                price_per_session=600
            ),
            Trainers(
                name="Марія Коваленко",
                specialization="Бокс",
                photo_url="https://i.pinimg.com/736x/4d/f9/ab/4df9abd7e1fd91e44827767e072071a2.jpg",
                rating=4.7,
                description="Чемпіонка України з боксу. Професійний тренер з індивідуальним підходом до кожного клієнта.",
                experience_years=7,
                price_per_session=700
            ),
            Trainers(
                name="Дмитро Сидоренко",
                specialization="Тренажерка",
                photo_url="https://i.pinimg.com/736x/1e/d9/c6/1ed9c602921a924ef195c631782ca581.jpg",
                rating=4.8,
                description="Фітнес-тренер з акцентом на силові тренування та набір м'язової маси.",
                experience_years=5,
                price_per_session=550
            ),
            Trainers(
                name="Анна Мельник",
                specialization="Йога",
                photo_url="https://i.pinimg.com/736x/91/1c/74/911c741961dcbacbeccf5c2031101124.jpg",
                rating=4.1,
                description="Сертифікований інструктор з аштанга-йоги та медитації.",
                experience_years=6,
                price_per_session=500
            ),
            Trainers(
                name="Володимир Шевченко",
                specialization="Бокс",
                photo_url="https://i.pinimg.com/736x/fe/50/19/fe50198f4262d3f9bac59c567fd29805.jpg",
                rating=4.9,
                description="Колишній професійний боксер, тепер тренує початківців та середній рівень.",
                experience_years=12,
                price_per_session=800
            )
        ]
        
        for trainer in trainers:
            db.add(trainer)
        
        subscriptions = [
            Subscriptions(
                name="Разове тренування",
                subscription_type=SubscriptionType.SINGLE.value,
                price=200.0,
                duration_days=1,
                visits_limit=1
            ),
            Subscriptions(
                name="Місяць Classic",
                subscription_type=SubscriptionType.MONTH_CLASSIC.value,
                price=1500.0,
                duration_days=30,
                visits_limit=None
            ),
            Subscriptions(
                name="Рік Gold",
                subscription_type=SubscriptionType.YEAR_GOLD.value,
                price=10000.0,
                duration_days=365,
                visits_limit=None
            )
        ]
        
        for subscription in subscriptions:
            db.add(subscription)
        
        db.commit()
        print("Дані успішно заповнено!")
        print(f"   - Створено {len(trainers)} тренерів")
        print(f"   - Створено {len(subscriptions)} абонементів")
        
    except Exception as e:
        db.rollback()
        print(f"Помилка при заповненні даних: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()

