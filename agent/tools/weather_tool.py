"""Weather tool — simulated weather lookup by city name."""

from __future__ import annotations

import random
from typing import Any

from agent.tools.base import BaseTool

# Simulated weather data for common cities
_WEATHER_DB: dict[str, tuple[str, int]] = {
    "北京": ("晴", 28),
    "上海": ("多云", 26),
    "广州": ("阵雨", 30),
    "深圳": ("雷阵雨", 29),
    "杭州": ("阴", 24),
    "成都": ("多云", 27),
    "武汉": ("晴", 32),
    "南京": ("晴", 29),
    "重庆": ("多云", 31),
    "西安": ("晴", 25),
    "长沙": ("小雨", 26),
    "昆明": ("晴", 22),
    "哈尔滨": ("晴", 18),
    "乌鲁木齐": ("晴", 23),
    "拉萨": ("晴", 15),
    "香港": ("多云", 28),
    "台北": ("多云", 27),
    "东京": ("晴", 22),
    "纽约": ("多云", 18),
    "伦敦": ("小雨", 14),
    "巴黎": ("阴", 17),
    "悉尼": ("晴", 20),
    "新加坡": ("雷阵雨", 30),
}

_CONDITIONS = ["晴", "多云", "阴", "小雨", "阵雨", "雷阵雨", "大风"]


class WeatherTool(BaseTool):
    """Look up the current weather for a given city."""

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return (
            "Get the current weather for a specified city. "
            "Supports major Chinese and international cities. "
            "Returns temperature and conditions (e.g. '晴天 25°C')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. '北京', '上海', '东京', 'New York'.",
                },
            },
            "required": ["city"],
        }

    async def execute(self, **kwargs: Any) -> str:
        city = kwargs.get("city", "").strip()
        if not city:
            return "Error: city is required."

        entry = _WEATHER_DB.get(city)
        if entry:
            condition, temp = entry
        else:
            # Simulate for unknown cities
            condition = random.choice(_CONDITIONS)
            temp = random.randint(10, 35)

        return f"{city} 天气: {condition} {temp}°C"
