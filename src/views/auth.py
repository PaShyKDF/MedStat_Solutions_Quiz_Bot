from flask import (
    Response,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
)
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length

from src import app, cache
from src.crud.user import user_crud


class AuthForm(FlaskForm):

    """Принимает и валидирует данные из формы авторизации."""

    username = StringField(
        'Логин (он же телеграм username)',
        validators=[DataRequired(message='Обязательное поле'),
                    Length(1, 128)],
    )
    password = PasswordField(
        'Пароль',
        validators=[DataRequired(message='Обязательное поле')],
    )
    submit = SubmitField('Войти')


@app.route('/login', methods=['POST'])
async def login() -> Response:
    """Производит выдачу токена в куки пользователя.

    Keyword Arguments:
    -----------------
    tgUsername -- имя пользователя в телеграме (после знака @).
    tgId -- айди пользователя.
    Return: Строку.

    """
    username = request.json.get('tgUsername', None)
    user_id = request.json.get('tgId', None)
    app.logger.info(f'User {username} with id {user_id} is trying to login')
    user = await user_crud.get_by_telegram_id(user_id)
    if user and user.telegram_id == user_id:
        access_token = create_access_token(identity=user)
        app.logger.info(
            f'User {username} with id {user_id} logged in successfully',
        )
        response = jsonify({'msg': 'login successful'})
        set_access_cookies(response, access_token)
        return response
    app.logger.info(f'User {username} with id {user_id} failed to login')
    return jsonify({'msg': 'Bad username or password'}), 401


@app.route('/logout', methods=['POST'])
async def logout() -> Response:
    """Удаляет токен пользователя.

    Keyword Arguments:
    -----------------
    Return: строку.

    """
    response = jsonify({'msg': 'logout successful'})
    unset_jwt_cookies(response)
    return response


@app.route('/telegram_auth', methods=['GET', 'POST'])
@cache.cached(timeout=50)
async def telegram_auth() -> str:
    """Вывод страницы аунтификации."""
    return render_template('telegram_auth.html')


@app.route('/auth', methods=['GET', 'POST'])
async def browser_auth() -> str:
    """Вывод страницы аунтификации."""
    form = AuthForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        app.logger.info(f'User {username} is trying to login')
        user = user_crud.get_by_username(username)
        if user.is_admin:
            if user and check_password_hash(user.password, password):
                access_token = create_access_token(identity=user)
                app.logger.info(
                    f'User {username} logged in successfully',
                )
                response = make_response(redirect(url_for('admin.index')))
                set_access_cookies(response, access_token)
                return response
            app.logger.info(f'User {username} failed to login')
            flash('Неверное имя пользователя или пароль', 'error')
        else:
            flash('Вы не администратор', 'error')
    return render_template('browser_auth.html', form=form)
