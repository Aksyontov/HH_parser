import asyncio
import json

import aiohttp
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Vacancy
from ..db import get_db
import gspread
from google.oauth2.service_account import Credentials

router = APIRouter()

API_URL = "https://api.hh.ru/vacancies"

scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_file(
    "/users/aksyontov/documents/hh_parser/vacancy-parser-435508-1ac85c60f6c6.json",
    scopes=scope)

client = gspread.authorize(creds)

sheet = client.open("HH Vacancy Export").sheet1

vacancy_store = {}


def extract_salary(salary):
    if salary:
        salary_min = salary.get('from') if salary.get('from') is not None else 0
        salary_max = salary.get('to') if salary.get('to') is not None else 0
        salary_currency = salary.get('currency', 'N/A')
    else:
        salary_min = 0
        salary_max = 0
        salary_currency = 'N/A'

    return salary_min, salary_max, salary_currency


def extract_professional_roles(professional_roles):
    if professional_roles:
        return ", ".join([role['name'] for role in professional_roles if 'name' in role])
    return 'N/A'


def create_vacancy(item, salary_min, salary_max, salary_currency, roles_name):
    return Vacancy(
        title=item.get('name'),
        city=item.get('area', {}).get('name', 'N/A'),
        specialization=roles_name,
        salary_min=salary_min,
        salary_max=salary_max,
        currency=salary_currency,
        url=item.get('alternate_url')
    )


async def fetch_all_vacancies():
    params = {
        "per_page": 100,
        "page": 0,
    }

    all_vacancies = []

    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(API_URL, params=params) as response:
                data = await response.json()
                all_vacancies.extend(data['items'])
                if data['page'] >= data['pages'] - 1:
                    break
                params['page'] += 1

    return all_vacancies


@router.post("/parse")
async def parse_vacancies(db: AsyncSession = Depends(get_db)):
    await db.execute(text("DELETE FROM vacancies"))
    await db.commit()

    data = await fetch_all_vacancies()

    for item in data:
        salary_min, salary_max, salary_currency = extract_salary(item.get('salary'))
        roles_name = extract_professional_roles(item.get('professional_roles', []))
        vacancy = create_vacancy(item, salary_min, salary_max, salary_currency, roles_name)
        db.add(vacancy)

    await db.commit()

    return {"status": "completed"}



@router.get("/vacancies")
async def get_vacancies(
    city: str = None,
    specialization: str = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Vacancy)

    if city:
        stmt = stmt.where(Vacancy.city == city)
    if specialization:
        stmt = stmt.where(Vacancy.specialization.like(f"%{specialization}%"))

    result = await db.execute(stmt)
    vacancies = result.scalars().all()

    vacancy_store['filtered_vacancies'] = vacancies

    return vacancies


@router.post("/export")
async def export_to_google_sheets():
    vacancies = vacancy_store.get('filtered_vacancies', [])

    if not vacancies:
        return {"error": "No vacancies to export. Please run the search first."}

    vacancies = sorted(vacancies, key=lambda v: (v.currency != "RUR", v.salary_min if v.currency == "RUR" else float('inf')))

    sheet.clear()

    data = [["Title", "City", "Specialization", "Min Salary", "Max Salary", "Currency", "URL"]]

    for vacancy in vacancies:
        data.append([
            vacancy.title,
            vacancy.city,
            vacancy.specialization,
            vacancy.salary_min,
            vacancy.salary_max,
            vacancy.currency,
            vacancy.url
        ])

    sheet.append_rows(data)

    return {"status": "exported"}

