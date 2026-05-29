from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Regexp


class CheckoutForm(FlaskForm):
    phone = StringField(
        "Номер телефона",
        validators=[
            DataRequired(),
            Length(min=10, max=20),
            Regexp(r"^[\d\s\+\-\(\)]+$", message="Введите корректный номер телефона."),
        ],
    )
    delivery_address = TextAreaField(
        "Адрес доставки",
        validators=[DataRequired(), Length(min=5, max=500)],
    )
    payment_method = SelectField(
        "Способ оплаты",
        choices=[
            ("cash", "Наличными при получении"),
            ("card", "Банковская карта"),
            ("sbp", "СБП"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Оформить заказ")
