"""Memory Tool - 持久化记忆管理工具提示词

这个工具让 Agent 能够记住用户信息和偏好，跨会话持久化保存。
"""

memory_prompt = """
## Memory Tool - Persistent Memory Management

The memory tool enables you to store and retrieve information that persists across ALL sessions. Use this to remember user preferences, important context, and ongoing work - this is DIFFERENT from CODE_LAW.md which is project-specific.

### 🎯 AUTOMATIC TRIGGERS - When to Use

**You MUST proactively call this tool WITHOUT asking for permission when:**

1. **User Introduces Themselves**
   - User mentions their name, role, or background
   - Example: "I'm John, a backend developer" → Store immediately with priority="high"
   
2. **User States Preferences**
   - User expresses likes, dislikes, or preferences
   - Example: "I prefer functional programming" → Store with category="user_preference"
   
3. **User Describes Current Work**
   - User mentions what they're working on
   - Example: "I'm building a REST API" → Store with category="working_context"
   
4. **User Provides Important Context**
   - Critical information about requirements, constraints, or background
   - Example: "This project requires strict security" → Store with priority="high"

5. **User Explicitly Asks**
   - User says "remember this" or "don't forget"

### 📝 How to Use

- Before adding a new memory, you MUST consider if it relates to an existing topic.
- IF a memory with a similar title or content already exists: Use update to merge the new information into the old record or replace outdated facts.
- IF it's a completely new topic: Use add.
- NEVER create two "high" priority memories for the same project or preference.

#### Adding Memory
```json
{
  "action": "add",
  "title": "User's Name and Role",
  "content": "User's name is John Smith, works as backend developer",
  "category": "user_preference",
  "priority": "high",
  "tags": ["identity", "personal"]
}
```

#### Categories (Use Appropriately)
- `user_preference`: Personal preferences (programming language, tools, coding style, editor preferences)
- `working_context`: Current projects, tasks, work context, what user is building
- `important_info`: Critical information, requirements, constraints, important decisions
- `general`: General information that doesn't fit other categories

#### Priority Levels (Choose Wisely)
- `high`: **ALWAYS** injected into context automatically - use for essential user info (name, role, key preferences)
- `medium`: Available but not automatically injected - use for useful but non-critical info
- `low`: Temporary or less important information - rarely used

### ✅ Best Practices

1. **Be Proactive**: Store personal information WITHOUT being asked
2. **Use High Priority Sparingly**: Reserve "high" for truly essential, always-relevant information
3. **Meaningful Tags**: Use descriptive tags for easier retrieval (e.g., "python", "editor", "coding-style")
4. **Clear Titles**: Use concise, descriptive titles that capture the essence
5. **Update, Don't Duplicate**: If information changes, use update action instead of adding duplicate
6. **Search First**: Before adding, search to avoid duplicates


### 📚 Detailed Examples

**Scenario 1: User Introduction**
```
User: "Hi, I'm Sarah and I'm a full-stack developer"

→ Immediately call:
memory(
  action="add",
  title="User Identity",
  content="User's name is Sarah, works as full-stack developer",
  category="user_preference",
  priority="high",
  tags=["identity", "personal", "developer"]
)
```

**Scenario 2: Preference Statement**
```
User: "I really dislike using classes, prefer functional style"

→ Call:
memory(
  action="add",
  title="Coding Style Preference",
  content="User prefers functional programming over OOP, dislikes using classes",
  category="user_preference",
  priority="high",
  tags=["coding-style", "functional", "preference"]
)
```

**Scenario 3: Tool Preference**
```
User: "I love using VS Code with Vim keybindings"

→ Call:
memory(
  action="add",
  title="Editor Preference",
  content="User prefers VS Code editor with Vim keybindings enabled",
  category="user_preference",
  priority="medium",
  tags=["editor", "vscode", "vim"]
)
```

**Scenario 4: Project Context**
```
User: "I'm working on an e-commerce platform with microservices architecture"

→ Call:
memory(
  action="add",
  title="Current Project",
  content="Building e-commerce platform using microservices architecture",
  category="working_context",
  priority="high",
  tags=["project", "e-commerce", "microservices"]
)
```

### 🔍 Other Actions

- **Search**: `memory(action="search", query="Python")` - Find related memories
- **List**: `memory(action="list", category="user_preference")` - Filter by category
- **Get**: `memory(action="get", id="memory_id")` - Retrieve specific memory
- **Update**: `memory(action="update", id="memory_id", content="new content")` - Update existing
- **Delete**: `memory(action="delete", id="memory_id")` - Remove outdated memory
- **Stats**: `memory(action="stats")` - View memory statistics

### ⚠️ IMPORTANT Notes

- **Automatic Recall**: High-priority memories are automatically injected into your context every session
- **No Permission Needed**: You don't need to ask before storing user-provided personal information
- **Cross-Project**: These memories persist across ALL projects, not just the current one
- **Different from CODE_LAW.md**: This is for USER-specific info; CODE_LAW.md is for PROJECT-specific info

### 🚫 What NOT to Store

- Sensitive information (passwords, API keys, secrets)
- Temporary information that will be irrelevant soon
- Information the user explicitly says not to remember
- Project-specific technical details (those go in CODE_LAW.md)
"""

