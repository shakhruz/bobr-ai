"""Темы. Готова одна: дроби, сложение с разными знаменателями. Ещё две — заготовки."""
from dataclasses import dataclass, field
from fractions import Fraction


@dataclass
class Task:
    text: str          # "1/2 + 1/3"
    answer: Fraction   # правильный ответ (несократимый)


def _t(a: str, b: str) -> Task:
    x, y = Fraction(a), Fraction(b)
    return Task(f"{a} + {b}", x + y)


@dataclass
class Topic:
    key: str
    title: str
    ready: bool
    intro: str                      # что Бобр «слышал» о теме (без ответа)
    method: str                     # эталонный метод (знает классификатор и Хумо, Бобр — нет)
    tasks: list[Task] = field(default_factory=list)
    teach_idx: int = 0              # задача, которую Бобр приносит первой
    apply_idx: list[int] = field(default_factory=list)   # задачи «по объяснению»
    test_idx: list[int] = field(default_factory=list)    # контрольная
    mistakes: dict[str, str] = field(default_factory=dict)  # kind -> типичная ошибка 5-классника


FRACTIONS = Topic(
    key="fractions_add",
    title="Kasrlar: maxrajlari har xil kasrlarni qoʻshish",
    ready=True,
    intro="Bobr kasrlarni qoʻshishni bilmaydi: 1/2 + 1/3 ni qanday hisoblashni ustozdan soʻraydi.",
    method=(
        "1) Найти общий знаменатель (НОК знаменателей). "
        "2) Привести каждую дробь к нему: числитель и знаменатель умножить на ОДИН И ТОТ ЖЕ дополнительный множитель. "
        "3) Сложить только числители, знаменатель оставить общий. "
        "4) Сократить результат, если можно. Пример: 1/2 + 1/3 = 3/6 + 2/6 = 5/6."
    ),
    tasks=[
        _t("1/2", "1/3"),    # 0 teach
        _t("1/4", "1/6"),    # 1 apply (НОК 12)
        _t("2/3", "1/6"),    # 2 apply
        _t("1/6", "1/3"),    # 3 apply (нужно сократить 3/6)
        _t("3/4", "1/8"),    # 4 test
        _t("2/5", "1/10"),   # 5 test (сократить 5/10)
        _t("1/3", "1/4"),    # 6 test
        _t("1/6", "3/4"),    # 7 запас
    ],
    teach_idx=0,
    apply_idx=[1, 2, 3],
    test_idx=[4, 5, 6],
    mistakes={
        "add_both": "складывает и числители, и знаменатели: 1/2 + 1/3 = 2/5",
        "no_common_den": "складывает числители и оставляет знаменатель одной из дробей без приведения: 1/2 + 1/3 = 2/3",
        "lcm_error": "ошибается в общем знаменателе: берёт сумму или произведение знаменателей не по делу, либо путает НОК (для 4 и 6 берёт 24 или 10)",
        "bad_multiply": "умножает на дополнительный множитель только знаменатель (или только числитель): 1/2 -> 1/6 вместо 3/6",
        "no_reduce": "не сокращает ответ: оставляет 3/6 вместо 1/2",
    },
)

DECIMALS = Topic(
    key="decimals", title="Oʻnli kasrlar (tez orada)", ready=False,
    intro="Заготовка: десятичные дроби — сравнение и сложение в столбик.",
    method="Выровнять запятые, дописать нули, складывать как натуральные, запятую снести вниз.",
    mistakes={
        "longer_is_bigger": "считает, что 0,25 больше 0,3, потому что «25 больше 3»",
        "comma_misaligned": "пишет в столбик по правому краю, запятые не выровнены: 0,5 + 0,25 = 0,30",
    },
)

PERCENT = Topic(
    key="percent", title="Foizlar (tez orada)", ready=False,
    intro="Заготовка: проценты — найти процент от числа.",
    method="1% = сотая часть числа; p% от N = N : 100 · p.",
    mistakes={
        "percent_is_number": "считает 20% от 50 как 50 − 20 = 30",
        "wrong_division": "делит на процент вместо деления на 100: 20% от 50 = 50 : 20",
    },
)

TOPICS = {t.key: t for t in (FRACTIONS, DECIMALS, PERCENT)}
DEFAULT_TOPIC = FRACTIONS.key


def get_topic(key: str) -> Topic:
    return TOPICS.get(key, FRACTIONS)


def fmt_fraction(f: Fraction) -> str:
    return f"{f.numerator}/{f.denominator}"
