# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered interactive historical fiction game built with Streamlit. Players can "transmigrate" into classic Chinese literature (Three Kingdoms, Water Margin) or historical periods (Ming Dynasty, Qing Dynasty), assuming the role of famous characters or creating custom ones. The game uses Alibaba's DashScope API with multiple app IDs for different story worlds.

## Core Architecture

### Main Application (`qwen_python.py`)

**State Management:**
- All game state stored in `st.session_state.game_state` with keys:
  - `points`, `achievements`, `scene_history`, `choice_history`, `points_history`
  - `current_scene`, `game_started`, `character_created`, `character_type`
  - `is_generating` - critical flag to prevent duplicate LLM calls
- Character data stored separately in `st.session_state.character_info`
- LLM session continuity maintained via `st.session_state.llm_session_id`

**LLM Integration Pattern:**
1. `call_llm_api_raw()` (qwen_python.py:246) - Streams raw text from DashScope API
   - Selects app_id based on `character_info['novel']` value
   - Maintains conversational context through session_id
   - Uses incremental streaming for real-time response
2. `parse_and_validate_json()` (qwen_python.py:302) - Extracts and validates JSON from LLM output
   - Expected structure: `{scene_description, choices[], game_update: {points_awarded, new_achievement}}`
   - Provides fallback choices if parsing fails

**Critical Generation Flow:**
- User action triggers `is_generating=True` flag (qwen_python.py:598)
- Next render cycle shows spinner and calls LLM (qwen_python.py:520-575)
- Scene description displays character-by-character with 0.02s delay for dramatic effect
- After completion, `is_generating=False` and state updates
- **Important:** Never call LLM directly in button callbacks; always use the two-step pattern to avoid duplicate calls

### Character System

**Preset Characters (`PRESET_CHARACTERS`, qwen_python.py:26-243):**
- Nested structure: `{novel -> character_name -> character_data}`
- Each character has `timeline_scenes` with timeline-specific `background` and `initial_scene`
- Dynamic background selection based on timeline (qwen_python.py:381-403)

**Timeline Configuration:**
- Three Kingdoms: 黄巾起义, 董卓乱政, 官渡之战, 赤壁之战, 三国鼎立, 北伐中原
- Water Margin: 洪太尉访道, 梁山聚义, 攻打祝家庄, 招安之路, 征讨方腊, 卸甲还乡
- Ming Dynasty: 洪武之治, 靖难之役, 永乐盛世, 土木堡之变, 万历乱局, 女真崛起, 闯王进京
- Qing Dynasty: 八旗入关, 康熙继位, 九子夺嫡, 马戛尔尼访华, 虎门销烟, 金田起义, 第二次中英战争, 洋务运动, 甲午战争, 八国联军进京, 预备立宪

### Environment Configuration

API credentials stored in `.env` file:
- `DASHSCOPE_API_KEY` - Main API key for Alibaba DashScope
- `SHUIHU_APP_ID` - Water Margin story app
- `SANGUO_APP_ID` - Three Kingdoms story app
- `MINGDAI_APP_ID` - Ming Dynasty story app
- `QINGDAI_APP_ID` - Qing Dynasty story app

**Security Note:** The `.env` file contains actual API keys and should never be committed to version control.

## Development Commands

### Running the Application

```bash
streamlit run qwen_python.py
```

Default configuration:
- Port: 8501
- Address: localhost
- Layout: wide mode with expanded sidebar

### Production Deployment

The `streamlit.service` file shows systemd configuration for production:
```bash
# Install service
sudo cp streamlit.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable streamlit
sudo systemctl start streamlit

# Check status
sudo systemctl status streamlit
```

### Dependencies

Install requirements:
```bash
pip install -r requirements.txt
```

Core dependencies:
- `streamlit` - Web interface
- `pandas` + `plotly` - Data visualization
- `dashscope` - Alibaba's LLM API
- `python-dotenv` - Environment variable management

## Key Implementation Details

### Avoiding Duplicate LLM Calls

The `is_generating` flag pattern is essential (qwen_python.py:520, 595):
- Button press sets flag and stores user action
- Next render detects flag, calls LLM once, resets flag
- Without this pattern, Streamlit's reactive model causes multiple API calls

### Streaming Display

Character-by-character rendering (qwen_python.py:546-552):
```python
scene_placeholder = st.empty()
displayed = ""
for char in scene_text:
    displayed += char
    scene_placeholder.markdown(f"### 📖 剧情发展\n\n{displayed}")
    time.sleep(0.02)
```

### Fallback Mechanisms

Multiple layers of error handling:
1. If API call fails, use preset fallback scene (qwen_python.py:529-534)
2. If JSON parsing fails, use alternative fallback (qwen_python.py:538-543)
3. If choices array missing/empty, provide default choices (qwen_python.py:315)

## Future Development Plans

According to `产品描述.md`, planned features include:
- **Backend migration:** FastAPI to replace Streamlit
- **Frontend rewrite:** Vue.js with minimalist CSS design
- **Authentication:** Phone/email login with password
- **Usage limits:**
  - Unauthenticated: 26 messages per day (IP/fingerprint based)
  - After login prompt: Additional 10 messages
  - Registration required for continued access

## Code Style Conventions

- Chinese comments and UI text throughout
- Scene descriptions and character backgrounds in classical Chinese style
- Consistent emoji usage for UI elements (🎮, 📖, 🎯, 💬, 🏆, 📈)
- Three-column layout pattern: context (left), main content (center), stats (right)
