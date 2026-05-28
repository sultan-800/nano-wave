from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class RegisterForm(FlaskForm):
    username = StringField("Имя пользователя", validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Пароль", validators=[DataRequired(), Length(min=6, max=128)])
    confirm_password = PasswordField(
        "Подтверждение пароля", validators=[DataRequired(), EqualTo("password", message="Пароли не совпадают.")]
    )
    submit = SubmitField("Зарегистрироваться")
