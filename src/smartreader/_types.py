from typing import Callable

from .types.content import Content
from .types.params import TriggerParams
from .types.values import StateValue

# success, error
Callback = Callable[[bool, str], None]

# success, error, result
StringCallback        = Callable[[bool, str, str], None]
ScoreCallback         = Callable[[bool, str, float], None]
ContentCallback       = Callable[[bool, str, Content], None]
ContentListCallback   = Callable[[bool, str, list[Content]], None]
TriggerCallback       = Callable[[bool, str, TriggerParams], None]
StateValueCallback    = Callable[[bool, str, StateValue], None]
FeedbackListCallback  = Callable[[bool, str, list[tuple[str, bool]]], None]
