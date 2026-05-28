from flask_wtf import FlaskForm
from wtforms import DecimalField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange


class ProductForm(FlaskForm):
    title = StringField("Название", validators=[DataRequired(), Length(min=2, max=200)])
    description = TextAreaField("Описание", validators=[DataRequired(), Length(min=5, max=2000)])
    price = DecimalField("Цена", validators=[DataRequired(), NumberRange(min=0)], places=2)
    image = StringField("Имя изображения", validators=[Length(max=255)])
    category = StringField("Категория", validators=[DataRequired(), Length(min=2, max=100)])
    stock = IntegerField("Остаток", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Сохранить")
