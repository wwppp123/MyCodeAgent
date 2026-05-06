"""Weather tool using Open-Meteo API (no API key required)."""

import json
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List

from tools.base import Tool, ToolParameter, ErrorCode


class WeatherTool(Tool):
    """Tool for querying weather information via Open-Meteo API.
    
    Open-Meteo is a free weather service that doesn't require API keys.
    Uses geocoding API to convert city names to coordinates.
    """

    CITY_COORDS = {
        "重庆": {"latitude": 29.5630, "longitude": 106.5516},
        "Chongqing": {"latitude": 29.5630, "longitude": 106.5516},
        "北京": {"latitude": 39.9042, "longitude": 116.4074},
        "Beijing": {"latitude": 39.9042, "longitude": 116.4074},
        "上海": {"latitude": 31.2304, "longitude": 121.4737},
        "Shanghai": {"latitude": 31.2304, "longitude": 121.4737},
        "广州": {"latitude": 23.1291, "longitude": 113.2644},
        "Guangzhou": {"latitude": 23.1291, "longitude": 113.2644},
        "深圳": {"latitude": 22.5431, "longitude": 114.0579},
        "Shenzhen": {"latitude": 22.5431, "longitude": 114.0579},
        "成都": {"latitude": 30.5728, "longitude": 104.0668},
        "Chengdu": {"latitude": 30.5728, "longitude": 104.0668},
        "武汉": {"latitude": 30.5928, "longitude": 114.3055},
        "Wuhan": {"latitude": 30.5928, "longitude": 114.3055},
        "南京": {"latitude": 32.0603, "longitude": 118.7969},
        "Nanjing": {"latitude": 32.0603, "longitude": 118.7969},
        "天津": {"latitude": 39.3434, "longitude": 117.3616},
        "Tianjin": {"latitude": 39.3434, "longitude": 117.3616},
        "杭州": {"latitude": 30.2741, "longitude": 120.1551},
        "Hangzhou": {"latitude": 30.2741, "longitude": 120.1551},
        "西安": {"latitude": 34.3416, "longitude": 108.9398},
        "Xi'an": {"latitude": 34.3416, "longitude": 108.9398},
        "香港": {"latitude": 22.3193, "longitude": 114.1694},
        "Hong Kong": {"latitude": 22.3193, "longitude": 114.1694},
        "澳门": {"latitude": 22.1987, "longitude": 113.5439},
        "Macau": {"latitude": 22.1987, "longitude": 113.5439},
        "台北": {"latitude": 25.0330, "longitude": 121.5654},
        "Taipei": {"latitude": 25.0330, "longitude": 121.5654},
        "吉林": {"latitude": 43.8721, "longitude": 126.5667},
        "Jilin": {"latitude": 43.8721, "longitude": 126.5667},
        "长春": {"latitude": 43.8868, "longitude": 125.3245},
        "Changchun": {"latitude": 43.8868, "longitude": 125.3245},
        "哈尔滨": {"latitude": 45.8038, "longitude": 126.5350},
        "Harbin": {"latitude": 45.8038, "longitude": 126.5350},
        "沈阳": {"latitude": 41.8057, "longitude": 123.4315},
        "Shenyang": {"latitude": 41.8057, "longitude": 123.4315},
        "大连": {"latitude": 38.9140, "longitude": 121.6147},
        "Dalian": {"latitude": 38.9140, "longitude": 121.6147},
        "济南": {"latitude": 36.6762, "longitude": 117.0009},
        "Jinan": {"latitude": 36.6762, "longitude": 117.0009},
        "青岛": {"latitude": 36.0671, "longitude": 120.3826},
        "Qingdao": {"latitude": 36.0671, "longitude": 120.3826},
        "郑州": {"latitude": 34.7466, "longitude": 113.6254},
        "Zhengzhou": {"latitude": 34.7466, "longitude": 113.6254},
        "长沙": {"latitude": 28.2282, "longitude": 112.9388},
        "Changsha": {"latitude": 28.2282, "longitude": 112.9388},
        "昆明": {"latitude": 24.8801, "longitude": 102.8329},
        "Kunming": {"latitude": 24.8801, "longitude": 102.8329},
        "贵阳": {"latitude": 26.5783, "longitude": 106.7135},
        "Guiyang": {"latitude": 26.5783, "longitude": 106.7135},
        "南宁": {"latitude": 22.8154, "longitude": 108.3275},
        "Nanning": {"latitude": 22.8154, "longitude": 108.3275},
        "福州": {"latitude": 26.0745, "longitude": 119.2965},
        "Fuzhou": {"latitude": 26.0745, "longitude": 119.2965},
        "厦门": {"latitude": 24.4798, "longitude": 118.0894},
        "Xiamen": {"latitude": 24.4798, "longitude": 118.0894},
        "南昌": {"latitude": 28.6766, "longitude": 115.9103},
        "Nanchang": {"latitude": 28.6766, "longitude": 115.9103},
        "合肥": {"latitude": 31.8206, "longitude": 117.2272},
        "Hefei": {"latitude": 31.8206, "longitude": 117.2272},
        "石家庄": {"latitude": 38.0423, "longitude": 114.5148},
        "Shijiazhuang": {"latitude": 38.0423, "longitude": 114.5148},
        "太原": {"latitude": 37.8706, "longitude": 112.5489},
        "Taiyuan": {"latitude": 37.8706, "longitude": 112.5489},
        "兰州": {"latitude": 36.0611, "longitude": 103.8343},
        "Lanzhou": {"latitude": 36.0611, "longitude": 103.8343},
        "西宁": {"latitude": 36.6171, "longitude": 101.7782},
        "Xining": {"latitude": 36.6171, "longitude": 101.7782},
        "银川": {"latitude": 38.4680, "longitude": 106.2731},
        "Yinchuan": {"latitude": 38.4680, "longitude": 106.2731},
        "呼和浩特": {"latitude": 40.8414, "longitude": 111.7519},
        "Hohhot": {"latitude": 40.8414, "longitude": 111.7519},
        "乌鲁木齐": {"latitude": 43.8256, "longitude": 87.6168},
        "Urumqi": {"latitude": 43.8256, "longitude": 87.6168},
        "拉萨": {"latitude": 29.6520, "longitude": 91.1721},
        "Lhasa": {"latitude": 29.6520, "longitude": 91.1721},
    }

    def __init__(self, project_root: str):
        super().__init__(
            name="weather",
            description="查询指定城市的天气信息。支持中文城市名（如：北京、上海、重庆）。无需 API Key。",
            project_root=Path(project_root)
        )

    def get_parameters(self) -> List[ToolParameter]:
        """Define tool parameters."""
        return [
            ToolParameter(
                name="city",
                type="string",
                description="城市名称，支持中文（北京、上海、重庆）或英文（London, Tokyo）",
                required=True,
            ),
            ToolParameter(
                name="format",
                type="string",
                description="输出格式：'simple'（单行摘要）或 'detailed'（详细报告），默认 'simple'",
                required=False,
                default="simple",
            ),
        ]

    def run(self, parameters: Dict[str, Any]) -> str:
        """Execute weather query.
        
        Args:
            parameters: Must contain 'city', optional 'format'
            
        Returns:
            JSON-formatted response following the Tool Response Protocol
        """
        start_time = time.time()
        
        city = parameters.get("city", "").strip()
        if not city:
            return self.create_error_response(
                error_code=ErrorCode.INVALID_PARAM,
                message="缺少必需参数：city（城市名称）",
                params_input=parameters,
                time_ms=int((time.time() - start_time) * 1000),
            )
        
        output_format = parameters.get("format", "simple")
        
        try:
            weather_data = self._fetch_weather(city)
            
            if output_format == "detailed":
                text = self._format_detailed(weather_data, city)
            else:
                text = self._format_simple(weather_data, city)
            
            return self.create_success_response(
                data=weather_data,
                text=text,
                params_input=parameters,
                time_ms=int((time.time() - start_time) * 1000),
                extra_stats={"source": "Open-Meteo"},
            )
            
        except urllib.error.HTTPError as e:
            return self.create_error_response(
                error_code=ErrorCode.INTERNAL_ERROR,
                message=f"天气服务请求失败：HTTP {e.code}",
                params_input=parameters,
                time_ms=int((time.time() - start_time) * 1000),
            )
        except urllib.error.URLError as e:
            return self.create_error_response(
                error_code=ErrorCode.INTERNAL_ERROR,
                message=f"网络连接失败：{e.reason}",
                params_input=parameters,
                time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return self.create_error_response(
                error_code=ErrorCode.INTERNAL_ERROR,
                message=f"查询天气时出错：{str(e)}",
                params_input=parameters,
                time_ms=int((time.time() - start_time) * 1000),
            )

    def _fetch_weather(self, city: str) -> Dict[str, Any]:
        """Fetch weather data from Open-Meteo API.
        
        Args:
            city: City name (supports Chinese)
            
        Returns:
            Parsed JSON weather data
        """
        latitude, longitude = self._get_city_coords(city)
        
        # Open-Meteo API endpoint
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitude}&longitude={longitude}"
            f"&current_weather=true"
            f"&temperature_unit=celsius"
            f"&windspeed_unit=kmh"
            f"&precipitation_unit=mm"
            f"&timezone=auto"
        )
        
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        data["city_name"] = city
        data["latitude"] = latitude
        data["longitude"] = longitude
        
        return data

    def _get_city_coords(self, city: str) -> tuple:
        """Get coordinates for a city.
        
        Args:
            city: City name
            
        Returns:
            Tuple of (latitude, longitude)
        """
        if city in self.CITY_COORDS:
            coords = self.CITY_COORDS[city]
            return coords["latitude"], coords["longitude"]
        
        return self._geocode_city(city)
    
    def _geocode_city(self, city: str) -> tuple:
        """Use Open-Meteo geocoding API to find city coordinates.
        
        Args:
            city: City name
            
        Returns:
            Tuple of (latitude, longitude)
        """
        try:
            encoded_city = urllib.parse.quote(city)
            url = (
                f"https://geocoding-api.open-meteo.com/v1/search?"
                f"name={encoded_city}&count=1&language=zh&format=json"
            )
            
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            results = data.get("results", [])
            if not results:
                raise Exception(f"未找到城市：{city}")
            
            result = results[0]
            latitude = result.get("latitude")
            longitude = result.get("longitude")
            
            if latitude is None or longitude is None:
                raise Exception(f"城市坐标无效：{city}")
            
            return latitude, longitude
            
        except urllib.error.HTTPError as e:
            raise Exception(f"地理编码服务请求失败：HTTP {e.code}")
        except urllib.error.URLError as e:
            raise Exception(f"地理编码网络连接失败：{e.reason}")
        except Exception as e:
            raise Exception(f"查找城市坐标时出错：{str(e)}")

    def _format_simple(self, data: Dict[str, Any], city: str) -> str:
        """Format simple one-line weather report."""
        try:
            current = data.get("current_weather", {})
            temp = current.get("temperature", "N/A")
            windspeed = current.get("windspeed", "N/A")
            
            weathercode = current.get("weathercode", 0)
            desc = self._weathercode_to_desc(weathercode)
            
            return f"🌤️ {city}：{desc}，温度 {temp}°C，风速 {windspeed} km/h"
        except Exception:
            return f"🌤️ {city}：天气数据解析失败"
    
    def _weathercode_to_desc(self, code: int) -> str:
        """Convert WMO weather code to Chinese description."""
        descriptions = {
            0: "晴朗",
            1: "少云",
            2: "部分多云",
            3: "阴天",
            45: "雾",
            48: "雾",
            51: "小雨",
            53: "中雨",
            55: "大雨",
            56: "小雨",
            57: "大雨",
            61: "小雨",
            63: "中雨",
            65: "大雨",
            66: "雨夹雪",
            67: "雪",
            71: "小雪",
            73: "中雪",
            75: "大雪",
            77: "雪",
            80: "阵雨",
            81: "中阵雨",
            82: "大阵雨",
            85: "阵雪",
            86: "大阵雪",
            95: "雷雨",
            96: "雷雨",
            99: "强雷雨",
        }
        return descriptions.get(code, "未知天气")

    def _format_detailed(self, data: Dict[str, Any], city: str) -> str:
        """Format detailed weather report."""
        lines = []
        lines.append("=" * 50)
        lines.append(f"🌤️ {city} 天气报告")
        lines.append("=" * 50)
        
        try:
            current = data.get("current_weather", {})
            
            temp = current.get("temperature", "N/A")
            lines.append(f"\n🌡️ 温度：{temp}°C")
            
            windspeed = current.get("windspeed", "N/A")
            lines.append(f"\n💨 风速：{windspeed} km/h")
            
            weathercode = current.get("weathercode", 0)
            desc = self._weathercode_to_desc(weathercode)
            lines.append(f"\n天气状况：{desc}")
            
            time_str = current.get("time", "N/A")
            lines.append(f"\n观测时间：{time_str}")
            
            lines.append("\n" + "=" * 50)
            
        except Exception as e:
            lines.append(f"\n解析天气数据时出错：{str(e)}")
        
        return "\n".join(lines)
