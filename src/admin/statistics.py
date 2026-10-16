from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
import requests
from celery import shared_task
from flask import Response, jsonify, redirect, request, url_for
from flask_admin import BaseView, expose
from flask_jwt_extended import (
    current_user,
    jwt_required,
    verify_jwt_in_request,
)
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from src.bot import bot
from src.crud.category import category_crud
from src.crud.excel_statistic import excel_statistic_crud
from src.crud.question import question_crud
from src.crud.quiz import quiz_crud
from src.crud.quiz_result import quiz_result_crud
from src.crud.telegram_user import telegram_user_crud
from src.crud.user import user_crud
from src.crud.user_answer import user_answer_crud


class OverAllStatisticsView(BaseView):

    """Обобщенная статистика."""

    @expose('/')
    @jwt_required()
    async def index(self) -> Response:
        """Обобщенная статистика."""
        verify_jwt_in_request()
        if not current_user.is_admin:
            return redirect(url_for('categories'))

        now = datetime.utcnow()
        last_day = now - timedelta(days=1)
        last_week = now - timedelta(weeks=1)
        last_month = now - timedelta(days=30)
        today_start = datetime(now.year, now.month, now.day)

        total_users = await user_crud.get_total_users()
        total_users_played_quiz = (
            await telegram_user_crud.get_total_users_played_quiz()
        )
        total_users_completed_quiz = (
            await telegram_user_crud.get_total_users_completed_quiz()
        )

        new_users_last_day = await user_crud.get_new_users_since(last_day)
        new_users_last_week = await user_crud.get_new_users_since(last_week)
        new_users_last_month = await user_crud.get_new_users_since(last_month)
        users_created_today = await user_crud.get_new_users_since(today_start)

        users_played_quiz_last_day = (
            await telegram_user_crud.get_users_played_quiz_since(last_day)
        )
        users_played_quiz_last_week = (
            await telegram_user_crud.get_users_played_quiz_since(last_week)
        )
        users_played_quiz_last_month = (
            await telegram_user_crud.get_users_played_quiz_since(last_month)
        )

        users_completed_quiz_last_day = (
            await telegram_user_crud.get_users_completed_quiz_since(last_day)
        )
        users_completed_quiz_last_week = (
            await telegram_user_crud.get_users_completed_quiz_since(last_week)
        )
        users_completed_quiz_last_month = (
            await telegram_user_crud.get_users_completed_quiz_since(last_month)
        )

        total_completed_quizzes = (
            await quiz_result_crud.get_total_completed_quizzes()
        )
        total_questions_answered = await user_answer_crud.get_total_answers()
        total_questions = await question_crud.get_total_questions()
        total_quizzes = await quiz_crud.get_total_quizzes()
        total_categories = await category_crud.get_total_categories()

        context = {
            'total_users': total_users,
            'total_users_played_quiz': total_users_played_quiz,
            'total_users_completed_quiz': total_users_completed_quiz,
            'new_users_last_day': new_users_last_day,
            'new_users_last_week': new_users_last_week,
            'new_users_last_month': new_users_last_month,
            'users_played_quiz_last_day': users_played_quiz_last_day,
            'users_played_quiz_last_week': users_played_quiz_last_week,
            'users_played_quiz_last_month': users_played_quiz_last_month,
            'users_completed_quiz_last_day': users_completed_quiz_last_day,
            'users_completed_quiz_last_week': users_completed_quiz_last_week,
            'users_completed_quiz_last_month': users_completed_quiz_last_month,
            'users_created_today': users_created_today,
            'total_completed_quizzes': total_completed_quizzes,
            'total_questions_answered': total_questions_answered,
            'total_questions': total_questions,
            'total_quizzes': total_quizzes,
            'total_categories': total_categories,
        }

        return self.render('admin/statistics.html', **context)

    @expose('/export', methods=['POST'])
    def export(self) -> Response:
        """Экспорт обобщенной статистики в Excel."""
        data = request.get_json()
        chat_id = data.get('chat_id')

        # Создание Excel файла
        save_to_excel.delay(chat_id)

        return jsonify(
            {'message': 'Файл скоро будет собран и отправлен в ваш чат.'},
        )


@shared_task(ignore_result=None)
def save_to_excel(chat_id: int) -> Response:
    """Сохраняет данные в Excel файл."""
    df_user_statistics = pd.DataFrame(
        excel_statistic_crud.get_user_quizzes_for_excel(),
    )
    df_answers = pd.DataFrame(
        excel_statistic_crud.get_user_answers_for_excel(),
    )
    df_quiz_results = pd.DataFrame(
        excel_statistic_crud.get_quiz_results_for_excel(),
    )
    df_category_statistics = pd.DataFrame(
        excel_statistic_crud.get_categories_for_excel(),
    )
    df_quiz_statistics = pd.DataFrame(
        excel_statistic_crud.get_quizzes_for_excel(),
    )
    df_question_statistics = pd.DataFrame(
        excel_statistic_crud.get_questions_for_excel(),
    )

    excel_file = BytesIO()
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # Устанавливаем начальный столбец для первого DataFrame
        start_col = 0

        if not df_user_statistics.empty:
            df_user_statistics.to_excel(
                writer,
                sheet_name='Статистика пользователей',
                index=False,
            )
            format_excel_columns(
                writer.sheets['Статистика пользователей'],
            )

        if not df_answers.empty:
            df_answers.to_excel(
                writer,
                sheet_name='Ответы на вопросы',
                index=False,
            )
            format_excel_columns(writer.sheets['Ответы на вопросы'])

        if not df_quiz_results.empty:
            df_quiz_results.to_excel(
                writer,
                sheet_name='Результаты всех викторин',
                index=False,
            )
            format_excel_columns(
                writer.sheets['Результаты всех викторин'],
            )

        # Цикл по каждому DataFrame
        for df in [
            df_category_statistics, df_quiz_statistics, df_question_statistics,
        ]:
            if not df.empty:
                # Записываем DataFrame в указанный начальный столбец
                df.to_excel(
                    writer,
                    sheet_name='Обобщенная статистика',
                    startcol=start_col,
                    index=False,
                )
                # Увеличиваем start_col для следующего DataFrame
                # (+1 для пустого столбца)
                start_col += len(df.columns) + 1

        # Форматируем столбцы с использованием вашей функции
        worksheet = writer.sheets['Обобщенная статистика']
        format_excel_columns(worksheet)

    excel_file.seek(0)  # Возврат к началу файла для чтения

    send_telegram_message_and_file(chat_id, excel_file)


def send_telegram_message_and_file(chat_id: int, file: BytesIO) -> None:
    """Отправляет сообщение и файл пользователю через Telegram API."""
    message = 'Экспорт завершен. Вот ваши данные.'

    response_message = requests.post(
        f'https://api.telegram.org/bot{bot.token}/sendMessage',
        data={'chat_id': chat_id, 'text': message},
    )

    if response_message.status_code != 200:
        raise Exception('Не удалось отправить сообщение в бот')

    current_datetime = datetime.now().strftime('%d-%m-%Y')
    response_file = requests.post(
        f'https://api.telegram.org/bot{bot.token}/sendDocument',
        data={'chat_id': chat_id},
        files={'document': (f'{current_datetime} exported_data.xlsx', file)},
    )

    if response_file.status_code != 200:
        raise Exception('Не удалось отправить файл в бот')


def format_excel_columns(worksheet: Worksheet) -> None:
    """Форматирование столбцов в Excel файле."""
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter

        # Установка стилей для заголовков
        if column[0].value is not None:
            column[0].font = Font(bold=True, color='000000', name='Calibri')
            column[0].fill = PatternFill(
                start_color='808080',
                end_color='808080',
                fill_type='solid',
            )
            column[0].alignment = Alignment(horizontal='center')
            column[0].border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin'),
            )

        for cell in column:
            if cell.value is not None:
                cell_length = len(str(cell.value))
                if cell_length > max_length:
                    max_length = cell_length

                # Установка выравнивания по центру для данных
                cell.alignment = Alignment(horizontal='center')

        adjusted_width = max_length + 2
        worksheet.column_dimensions[column_letter].width = adjusted_width

        # Добавление фильтра для каждого столбца
        worksheet.auto_filter.ref = worksheet.dimensions
