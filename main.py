from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import requests
import random
from database.db import engine, get_db, Base
from database.models import User

# Создаём таблицы в БД при старте
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Random Users App")


# Pydantic модели для ответов
class UserResponse(BaseModel):
    id: int
    gender: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    city: Optional[str]

    class Config:
        from_attributes = True


class LoadUsersRequest(BaseModel):
    count: int


def load_users_from_api(db: Session, count: int = 100):
    """Загружает пользователей из внешнего API"""
    try:
        print(f"Пытаемся загрузить {count} пользователей из API...")
        response = requests.get(f"https://api.randomdatatools.ru/?count={count}")
        response.raise_for_status()
        users_data = response.json()

        print(f"Получено {len(users_data)} записей из API")

        new_users_count = 0
        for user_data in users_data:
            gender = user_data.get('Gender', '')
            first_name = user_data.get('FirstName', '')
            last_name = user_data.get('LastName', '')
            phone = user_data.get('Phone', '')
            email = user_data.get('Email', '')
            city = user_data.get('City', '')

            unique_key = f"{email}_{phone}"

            existing_user = db.query(User).filter(User.email == email).first()

            if not existing_user:
                user = User(
                    gender=gender,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    email=email,
                    city=city,
                    external_id=unique_key
                )
                db.add(user)
                new_users_count += 1
                if new_users_count <= 3:
                    print(f"  Добавлен: {first_name} {last_name} ({gender}) - {email}")

        db.commit()
        print(f"Загружено {new_users_count} новых пользователей")
        return new_users_count
    except Exception as e:
        print(f"Ошибка при загрузке: {e}")
        import traceback
        traceback.print_exc()
        return 0


@app.on_event("startup")
def startup_event():
    """При запуске сервера загружаем 100 пользователей"""
    print("Запуск приложения...")
    try:
        db = next(get_db())
        count = db.query(User).count()
        print(f"Текущее количество пользователей в БД: {count}")

        if count == 0:
            print("База пуста, загружаем пользователей...")
            loaded = load_users_from_api(db, count=100)
            print(f"Загружено {loaded} пользователей")
        else:
            print(f"В базе уже есть {count} пользователей")
    except Exception as e:
        print(f"Ошибка при старте: {e}")


@app.get("/", response_class=HTMLResponse)
def root():
    """Главная страница с таблицей пользователей"""
    try:
        with open("static_index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Файл static_index.html не найден</h1>", status_code=404)


@app.get("/api/users")
def get_users(
        page: int = 1,
        limit: int = 20,
        db: Session = Depends(get_db)
):
    """API для получения пользователей с пагинацией"""
    if page < 1:
        page = 1
    if limit < 1 or limit > 100:
        limit = 20

    offset = (page - 1) * limit

    total = db.query(User).count()
    users = db.query(User).offset(offset).limit(limit).all()

    total_pages = (total + limit - 1) // limit if total > 0 else 1

    return {
        "users": [UserResponse.model_validate(user) for user in users],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }


@app.post("/api/load_users")
def load_users_endpoint(request_data: LoadUsersRequest, db: Session = Depends(get_db)):
    """Эндпоинт для загрузки дополнительных пользователей"""
    try:
        new_count = load_users_from_api(db, count=request_data.count)
        return {"message": f"Загружено {new_count} новых пользователей", "loaded": new_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/count")
def get_users_count(db: Session = Depends(get_db)):
    """Вспомогательный эндпоинт для проверки"""
    count = db.query(User).count()
    return {"total_users": count}


@app.get("/user/{user_id}", response_class=HTMLResponse)
def get_user_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    """Страница конкретного пользователя"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Пользователь не найден</title></head>
        <body>
            <h1>❌ Пользователь с ID {user_id} не найден</h1>
            <a href="/">← Вернуться на главную</a>
        </body>
        </html>
        """, status_code=404)

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{user.first_name} {user.last_name} - Профиль</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 32px; }}
            .header p {{ margin: 10px 0 0; opacity: 0.9; }}
            .content {{ padding: 40px; }}
            .info-row {{ display: flex; padding: 15px 0; border-bottom: 1px solid #eee; }}
            .info-label {{ font-weight: bold; width: 150px; color: #555; }}
            .info-value {{ flex: 1; color: #333; }}
            .back-link {{ display: inline-block; margin-top: 30px; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 8px; transition: background 0.3s; }}
            .back-link:hover {{ background: #764ba2; }}
            .random-link {{ display: inline-block; margin-left: 15px; padding: 12px 24px; background: #48bb78; color: white; text-decoration: none; border-radius: 8px; transition: background 0.3s; }}
            .random-link:hover {{ background: #38a169; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📄 Карточка пользователя</h1>
                <p>ID: {user.id}</p>
            </div>
            <div class="content">
                <div class="info-row">
                    <div class="info-label">👤 Пол:</div>
                    <div class="info-value">{user.gender or 'Не указан'}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">📛 Имя:</div>
                    <div class="info-value">{user.first_name or 'Не указано'}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">📛 Фамилия:</div>
                    <div class="info-value">{user.last_name or 'Не указано'}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">📞 Телефон:</div>
                    <div class="info-value">{user.phone or 'Не указан'}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">✉️ Email:</div>
                    <div class="info-value"><a href="mailto:{user.email}">{user.email or 'Не указан'}</a></div>
                </div>
                <div class="info-row">
                    <div class="info-label">🏠 Город:</div>
                    <div class="info-value">{user.city or 'Не указан'}</div>
                </div>
                <div>
                    <a href="/" class="back-link">← На главную</a>
                    <a href="/random" class="random-link">🎲 Случайный пользователь</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.get("/random", response_class=HTMLResponse)
def get_random_user(request: Request, db: Session = Depends(get_db)):
    """Страница случайного пользователя - при каждом обновлении новый пользователь"""
    total = db.query(User).count()

    if total == 0:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>Нет пользователей</title></head>
        <body>
            <h1>❌ В базе нет пользователей</h1>
            <a href="/">← Загрузите пользователей на главной странице</a>
        </body>
        </html>
        """, status_code=404)

    # Получаем случайного пользователя
    random_id = random.randint(1, total)
    user = db.query(User).filter(User.id == random_id).first()

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Случайный пользователь - {user.first_name} {user.last_name}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 32px; }}
            .header p {{ margin: 10px 0 0; opacity: 0.9; }}
            .content {{ padding: 40px; }}
            .info-row {{ display: flex; padding: 15px 0; border-bottom: 1px solid #eee; }}
            .info-label {{ font-weight: bold; width: 150px; color: #555; }}
            .info-value {{ flex: 1; color: #333; }}
            .back-link {{ display: inline-block; margin-top: 30px; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 8px; transition: background 0.3s; }}
            .back-link:hover {{ background: #764ba2; }}
            .random-link {{ display: inline-block; margin-left: 15px; padding: 12px 24px; background: #48bb78; color: white; text-decoration: none; border-radius: 8px; transition: background 0.3s; }}
            .random-link:hover {{ background: #38a169; }}
            .refresh-note {{ margin-top: 20px; padding: 10px; background: #e8f4f8; border-left: 4px solid #3498db; border-radius: 4px; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎲 Случайный пользователь</h1>
                <p>ID: {user.id}</p>
            </div>
            <div class="content">
                <div class="info-row">
                    <div class="info-label">👤 Пол:</div>
                    <div class="info-value">{user.gender or 'Не указан'}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">📛 Имя:</div>
                    <div class="info-value">{user.first_name or 'Не указано'}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">📛 Фамилия:</div>
                    <div class="info-value">{user.last_name or 'Не указано'}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">📞 Телефон:</div>
                    <div class="info-value">{user.phone or 'Не указан'}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">✉️ Email:</div>
                    <div class="info-value"><a href="mailto:{user.email}">{user.email or 'Не указан'}</a></div>
                </div>
                <div class="info-row">
                    <div class="info-label">🏠 Город:</div>
                    <div class="info-value">{user.city or 'Не указан'}</div>
                </div>
                <div>
                    <a href="/" class="back-link">← На главную</a>
                    <a href="/random" class="random-link">🎲 Другой случайный →</a>
                </div>
                <div class="refresh-note">
                    💡 Обновите страницу (F5) или нажмите "Другой случайный", чтобы увидеть нового пользователя.
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)