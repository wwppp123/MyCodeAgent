"""Weather Tool - 天气查询工具提示词

这个工具让 Agent 能够查询全球各地的实时天气信息。
"""

weather_prompt = """
## Weather Tool - Weather Information Query

Use this tool to get current weather information for any city worldwide. This tool uses wttr.in API which supports Chinese city names directly.

### 🎯 AUTOMATIC TRIGGERS - When to Use

**You MUST use this tool when:**

1. **User Asks About Weather**
   - User asks about weather conditions
   - Example: "今天重庆天气怎么样？" → Call weather tool with city="重庆"
   
2. **User Mentions Temperature/Climate**
   - Questions about temperature, humidity, wind speed
   - Example: "北京现在多少度？" → Call weather tool
   
3. **Travel/Outdoor Activity Planning**
   - User plans to travel or do outdoor activities
   - Example: "明天去上海穿什么衣服？" → Check weather first

### 📝 How to Use

#### Basic Query
```json
{
  "city": "Beijing",
  "format": "simple"
}
```

#### Detailed Report
```json
{
  "city": "上海",
  "format": "detailed"
}
```

### Supported Cities

- **Chinese cities**: 北京, 上海, 重庆, 广州, 深圳, 杭州, etc.
- **International cities**: London, Tokyo, New York, Paris, etc.
- **Airport codes**: PEK (Beijing), PVG (Shanghai), etc.

### Format Options

- `simple` (default): One-line summary like "重庆：25°C，晴朗，湿度 60%"
- `detailed`: Full report including temperature, humidity, pressure, wind, UV index

### 💡 Best Practices

1. **Always use Chinese city names** when user mentions them
2. **Extract city name** from user's question even if they use colloquial language
3. **Use format="detailed"** only when user needs detailed weather data
4. **No API key required** - this tool is free and always available
"""
