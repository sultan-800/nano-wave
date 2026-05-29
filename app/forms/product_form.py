from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DecimalField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ProductForm(FlaskForm):
    title = StringField("Название", validators=[DataRequired(), Length(min=2, max=200)])
    description = TextAreaField("Описание", validators=[DataRequired(), Length(min=5, max=2000)])
    price = DecimalField("Цена", validators=[DataRequired(), NumberRange(min=0)], places=2)
    image = StringField(
        "Имя файла изображения",
        validators=[Optional(), Length(max=255)],
        description="Например: iphone16pro.jpg",
    )
    image_file = FileField(
        "Загрузить изображение",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "gif", "webp", "svg"], "Только изображения")],
    )
    category = StringField("Категория", validators=[DataRequired(), Length(min=2, max=100)])
    stock = IntegerField("Остаток", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Сохранить")
