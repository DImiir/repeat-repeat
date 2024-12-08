from aiogram.filters.callback_data import CallbackData


class CallbackFactory(CallbackData, prefix='cb', sep='.'):
    other_days: str
    day: str
    action_id: int
    delete: int
    edit: int
