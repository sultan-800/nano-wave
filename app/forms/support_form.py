from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class SupportMessageForm(FlaskForm):
    message = TextAreaField("Ваше сообщение", validators=[DataRequired(), Length(min=3, max=2000)])
    submit = SubmitField("Отправить")
