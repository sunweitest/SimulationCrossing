import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import random
import time
from datetime import datetime
import os
import re
from http import HTTPStatus
from dashscope import Application
from dotenv import load_dotenv

load_dotenv()  # 从 .env 文件加载环境变量

# 设置页面
st.set_page_config(
    page_title="AI模拟穿越小说、历史",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 预设角色数据库
PRESET_CHARACTERS = {
    "三国演义": {
        "诸葛亮": {
            "name": "诸葛亮",
            "gender": "男性",
            "age": 35,
            "rank": "军师",
            "background": "字孔明，号卧龙，琅琊阳都人。三国时期蜀汉丞相，杰出的政治家、军事家、文学家。",
            "starting_points": 60,
            "timeline_scenes": {
                "赤壁之战": {
                    "background": "你正于东吴舌战群儒，力主孙刘联盟。周瑜对你又敬又忌，而你心中已有火攻之计。",
                    "initial_scene": "你站在东吴大营外，江风凛冽。周瑜刚刚召见你，问：‘孔明先生，若用火攻，当如何？’"
                },
                "北伐中原": {
                    "background": "你已六出祁山。但为报先帝之托，仍坚持北伐，帐中烛火彻夜不熄。",
                    "initial_scene": "五丈原秋风萧瑟，你卧于榻上，仍手执羽扇调度军务。姜维入帐急报：‘魏军压境！’"
                },
                "三国鼎立": {
                    "background": "蜀汉已立，你坐镇成都，内修政理，外联东吴，时刻警惕曹魏动向。",
                    "initial_scene": "成都丞相府内，你正审阅各地奏章。忽有快马急报：‘东吴欲背盟，联络曹魏！’"
                }
            }
        },
        "赵云": {
            "name": "赵云",
            "gender": "男性",
            "age": 32,
            "rank": "将军",
            "background": "字子龙，常山真定人。身长八尺，姿颜雄伟，蜀汉名将，以忠勇著称。",
            "starting_points": 45,
            "timeline_scenes": {
                "赤壁之战": {
                    "background": "你随刘备驻扎夏口，虽未直接参战，但已展现出非凡胆略。",
                    "initial_scene": "夏口江边，你奉命护送刘备家眷。远处赤壁火光冲天，喊杀声震耳欲聋。"
                },
                "三国鼎立": {
                    "background": "你镇守江州，威名远播，百姓称颂‘一身是胆’。",
                    "initial_scene": "江州城头，你巡视防务。斥候来报：‘魏将张郃率军逼近边境！’"
                }
            }
        },
        "曹操": {
            "name": "曹操",
            "gender": "男性",
            "age": 40,
            "rank": "丞相",

            "background": "字孟德，小字阿瞒，沛国谯县人。东汉末年杰出政治家、军事家、文学家。魏武帝",
            "starting_points": 65,
            "timeline_scenes": {
                "官渡之战": {
                    "background": "你与袁绍对峙于官渡，粮草将尽，但已定下奇袭乌巢之计。",
                    "initial_scene": "官渡大营中，你召集众将议事。荀彧献计：‘明公，当速袭乌巢！’"
                },
                "赤壁之战": {
                    "background": "你率百万大军南下，意图一统江南，但军中疫病流行，水战不利。",
                    "initial_scene": "长江北岸，你眺望对岸联军。程昱谏言：‘丞相，东吴有周瑜、诸葛亮，不可轻敌。’"
                }
            }
        }
    },
    "水浒传": {
        "宋江": {
            "name": "宋江",
            "gender": "男性",
            "age": 38,
            "rank": "小吏",
            "background": "字公明，绰号呼保义、及时雨，梁山一百单八将之首。",
            "starting_points": 55,
            "timeline_scenes": {
                "梁山聚义": {
                    "background": "你刚上梁山，晁盖尚在，众好汉对你既敬且疑。",
                    "initial_scene": "聚义厅中，你初见林冲、武松等好汉。晁盖举杯道：‘今日得公明兄上山，梁山如虎添翼！’"
                },
                "招安之路": {
                    "background": "你力主招安，但兄弟们多有不满，梁山内部暗流涌动。",
                    "initial_scene": "忠义堂内，李逵怒吼：‘哥哥若去东京，我便杀尽那帮狗官！’众头领面面相觑。"
                }
            }
        },
        "武松": {
            "name": "武松",
            "gender": "男性",
            "age": 28,
            "rank": "步军头领",
            "background": "绰号行者，又称武二郎，景阳冈打虎英雄，勇猛刚烈，义薄云天。",
            "starting_points": 46,
            "timeline_scenes": {
                "梁山聚义": {
                    "background": "你刚上梁山，因打虎、杀西门庆之名，备受敬重。",
                    "initial_scene": "你站在沙滩上，望着浩渺水泊。鲁智深拍你肩膀：‘兄弟，今后咱们并肩作战！’"
                },
                "攻打祝家庄": {
                    "background": "你随军攻打祝家庄，展现勇武，但心中对梁山前途有所疑虑。",
                    "initial_scene": "祝家庄外，你手持戒刀，准备冲锋。宋江下令：‘武松兄弟，你带一队人马从东门杀入！’"
                }
            }
        },
        "林冲": {
            "name": "林冲",
            "gender": "男性",
            "age": 35,
            "rank": "马军头领",
            "background": "绰号豹子头，原为东京八十万禁军教头，武艺高强，上梁山。",
            "starting_points": 50,
            "timeline_scenes": {
                "梁山聚义": {
                    "background": "你已被上梁山，但心中对朝廷仍有眷恋，郁郁寡欢。",
                    "initial_scene": "梁山泊中，你独自练枪。晁盖走来道：‘林教头，今日我等替天行道，何不畅饮？’"
                },
                "招安之路": {
                    "background": "你对招安持保留态度，经历官场，深知朝廷腐败。",
                    "initial_scene": "忠义堂内，当宋江提出招安，你沉默不语，手中酒杯微微颤抖。"
                }
            }
        }
    },
    "明代": {
        "朱元璋": {
            "name": "朱元璋",
            "gender": "男性",
            "age": 40,
            "rank": "皇帝",
            "background": "明朝开国皇帝，年号洪武，布衣出身，建立大明王朝。",
            "starting_points": 70,
            "timeline_scenes": {
                "洪武之治": {
                    "background": "你已登基为帝，大力反腐，整顿吏治，但诛杀功臣，朝中人心惶惶。",
                    "initial_scene": "南京皇宫中，你批阅奏章，锦衣卫指挥使毛骧跪报：‘胡惟庸结党营私，证据确凿！’"
                }
            }
        },
        "朱棣": {
            "name": "朱棣",
            "gender": "男性",
            "age": 35,
            "rank": "燕王/皇帝",
            "background": "明成祖，朱元璋第四子，原为燕王，通过靖难之役夺取皇位，年号永乐。",
            "starting_points": 65,
            "timeline_scenes": {
                "靖难之役": {
                    "background": "你以清君侧为名，起兵反抗建文帝，战事胶着。",
                    "initial_scene": "北平燕王府，你召集姚广孝等谋士。道衍和尚说：‘殿下，当速取南京！’"
                },
                "永乐盛世": {
                    "background": "你已登基，迁都北京，派郑和下西洋，修《永乐大典》，国力强盛。",
                    "initial_scene": "北京紫禁城中，你接见郑和：‘三宝，此次下西洋，当扬我国威！’"
                }
            }
        },
        "张居正": {
            "name": "张居正",
            "gender": "男性",
            "age": 45,
            "rank": "首辅",
            "background": "字叔大，明代杰出政治家，推行万历新政，改革赋税。",
            "starting_points": 60,
            "timeline_scenes": {
                "万历乱局": {
                    "background": "你作为首辅，大力改革，但权倾朝野，引来朝中非议。",
                    "initial_scene": "文渊阁中，你审阅考成法奏章。小皇帝万历在一旁读书，太后垂帘听政。"
                }
            }
        }
    },
    "清代": {
        "康熙": {
            "name": "康熙",
            "gender": "男性",
            "age": 20,
            "rank": "皇帝",
            "background": "爱新觉罗·玄烨，清朝第四位皇帝，年号康熙，开创康乾盛世。",
            "starting_points": 70,
            "timeline_scenes": {
                "康熙继位": {
                    "background": "你年幼登基，权臣鳌拜专权，你暗中积蓄力量。",
                    "initial_scene": "紫禁城乾清宫，你与祖母孝庄太后密谈。太后低语：‘玄烨，鳌拜势大，当谨慎行事。’"
                },
                "九子夺嫡": {
                    "background": "你年事已高，诸皇子争夺储位，朝局动荡。",
                    "initial_scene": "畅春园中，你卧病在床，听闻胤禩、胤禛等皇子结党营私，心中忧愤。"
                }
            }
        },
        "林则徐": {
            "name": "林则徐",
            "gender": "男性",
            "age": 50,
            "rank": "钦差大臣",
            "background": "字元抚，清代政治家、思想家，虎门销烟主持者。其行为也引起了中英战争",
            "starting_points": 55,
            "timeline_scenes": {
                "虎门销烟": {
                    "background": "你奉命赴广东禁烟，面对英商狡诈和朝廷压力，毅然销毁大烟。",
                    "initial_scene": "虎门海滩，你下令销毁大烟。洋商抗议，你厉声道：‘大烟流毒，害我中华！’"
                }
            }
        },
        "李鸿章": {
            "name": "李鸿章",
            "gender": "男性",
            "age": 60,
            "rank": "直隶总督",
            "background": "字渐甫，号少荃，晚清重臣，洋务运动主要领导人，北洋水师创建者。",
            "starting_points": 60,
            "timeline_scenes": {
                "洋务运动": {
                    "background": "你大力推行洋务，创办江南制造局、轮船招商局等，以求自强。",
                    "initial_scene": "天津直隶总督府，你与盛宣怀商议：‘当兴办铁路、电报，以固国本。’"
                },
                "甲午战争": {
                    "background": "朝鲜动乱，你派军前往朝鲜平叛",
                    "initial_scene": "朝鲜动乱，你派军前往朝鲜平叛"
                }
            }
        }
    }}

# === 新增：流式调用原始文本 ===
def call_llm_api_raw(user_input, current_scene, character_info):
    """流式调用 DashScope，返回完整原始响应文本（字符串）"""
    if 'llm_session_id' not in st.session_state:
        st.session_state.llm_session_id = None
    effective_background = character_info.get('dynamic_background') or character_info.get('background', '无')

    prompt = f"""
    玩家扮演的角色信息如下：
    - 姓名：{character_info['name']}
    - 身份：{character_info['rank']}
    - 背景：{effective_background}
    - 所处世界：{character_info['novel']}，
    - 时间节点：{character_info['timeline']}
    玩家做出选择或行动：「{user_input}」
    """.strip()

    if character_info['novel'] == "三国演义":
        app_id = os.getenv("SANGUO_APP_ID")
    elif character_info['novel'] == "水浒传":
        app_id = os.getenv("SHUIHU_APP_ID")
    elif character_info['novel'] == "明代":
        app_id = os.getenv("MINGDAI_APP_ID")
    elif character_info['novel'] == "清代":
        app_id = os.getenv("QINGDAI_APP_ID")

    full_text = ""
    session_id = st.session_state.llm_session_id
    print(prompt)
    try:
        responses = Application.call(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            app_id=app_id,
            prompt=prompt,
            session_id=session_id,
            stream=True,
            incremental_output=True
        )

        for response in responses:
            if response.status_code != HTTPStatus.OK:
                st.error(f"LLM 调用失败: {response.message} (code={response.status_code})")
                return None

            if response.output.text:
                full_text += response.output.text

            if hasattr(response.output, 'session_id') and response.output.session_id:
                st.session_state.llm_session_id = response.output.session_id
        print(full_text)
        return full_text

    except Exception as e:
        st.warning(f"调用异常: {e}")
        return None

# === 新增：解析 JSON ===
def parse_and_validate_json(raw_text):
    """从原始文本中提取并验证 JSON"""
    if not raw_text:
        return None
    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if not json_match:
        return None
    try:
        result = json.loads(json_match.group())
        required = ['scene_description', 'choices', 'game_update']
        if not all(k in result for k in required):
            return None
        if not isinstance(result['choices'], list) or len(result['choices']) == 0:
            result['choices'] = ["继续探索", "寻求帮助", "随机应变"]
        game_update = result.setdefault('game_update', {})
        game_update.setdefault('points_awarded', 5)
        game_update.setdefault('new_achievement', "")
        return result
    except Exception as e:
        st.warning(f"JSON 解析失败: {e}")
        return None

# 初始化游戏状态
def initialize_game_state():
    if 'game_state' not in st.session_state:
        st.session_state.game_state = {
            'points': 0,
            'achievements': [],
            'scene_history': [],
            'choice_history': [],
            'points_history': [],
            'current_scene': None,
            'game_started': False,
            'character_created': False,
            'character_type': None,
            'is_generating': False  # 新增：防止重复生成
        }

# 创建角色
def create_character():
    st.title("🎮 穿越模拟 - 角色创建")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("选择穿越设定")
        novels = list(PRESET_CHARACTERS.keys())
        selected_novel = st.selectbox("选择小说/历史背景", novels)

        if selected_novel == "三国演义":
            timelines = ["黄巾起义", "董卓乱政", "官渡之战", "赤壁之战", "三国鼎立", "北伐中原"]
        elif selected_novel == "水浒传":
            timelines = ["洪太尉访道", "梁山聚义", "攻打祝家庄", "招安之路", "征讨方腊", "卸甲还乡"]
        elif selected_novel == "明代":
            timelines = ["洪武之治", "靖难之役", "永乐盛世", "土木堡之变", "万历乱局", "女真崛起", "闯王进京"]
        elif selected_novel == "清代":
            timelines = ["八旗入关", "康熙继位", "九子夺嫡", "马戛尔尼访华", "虎门销烟", "金田起义", "第二次中英战争",
                         "洋务运动", "甲午战争", "八国联军进京", "预备立宪"]
        else:
            timelines = ["开端", "发展", "高潮", "结局"]
        selected_timeline = st.selectbox("选择时间节点", timelines)

        st.subheader("选择角色类型")
        character_type = st.radio(
            "选择角色创建方式",
            ["选择已有角色", "创建自定义角色"],
            horizontal=True
        )
        character_info = {}
        if character_type == "选择已有角色":
            if selected_novel in PRESET_CHARACTERS:
                preset_chars = PRESET_CHARACTERS[selected_novel]
                char_names = list(preset_chars.keys())
                selected_char_name = st.selectbox("选择角色", char_names)
                if selected_char_name:
                    base_info = preset_chars[selected_char_name]
                    character_info = base_info.copy()
                    character_info['novel'] = selected_novel
                    character_info['timeline'] = selected_timeline

                    # 动态获取 timeline-specific 背景和初始场景
                    timeline_scenes = base_info.get('timeline_scenes', {})
                    timeline_config = timeline_scenes.get(selected_timeline)

                    if timeline_config:
                        # 使用时间节点定制内容
                        display_background = timeline_config['background']
                        initial_scene_desc = timeline_config['initial_scene']
                    else:
                        # 回退到通用背景
                        display_background = base_info['background']
                        initial_scene_desc = f"你穿越到了{selected_novel}的{selected_timeline}时期，成为了{character_info['name']}。{base_info['background']}。你需要决定下一步的行动"

                    character_info['dynamic_background'] = display_background  # 保存动态背景
                    character_info['initial_scene_desc'] = initial_scene_desc
                    # 显示信息
                    st.info(
                        f"**角色信息:** {character_info['name']}，{character_info['gender']}，{character_info['age']}岁，{character_info['rank']}")
                    st.write(f"**背景:** {display_background}")
                    st.write(f"**初始积分:** {character_info.get('starting_points', 0)}")

                    # 保存动态背景用于后续（可选）
                    character_info['dynamic_background'] = display_background
                    character_info['initial_scene_desc'] = initial_scene_desc
            else:
                st.warning("该世界暂无预设角色，请选择自定义角色")
                character_type = "创建自定义角色"

        if character_type == "创建自定义角色":
            st.subheader("创建你的角色")
            col1a, col2a = st.columns(2)
            with col1a:
                character_name = st.text_input("角色姓名", value="未知")
                character_gender = st.selectbox("性别", ["男性", "女性"])
            with col2a:
                character_age = st.slider("年龄", 18, 60, 20)
                character_rank = st.selectbox("初始身份", [
                    "将军", "军师", "士兵", "斥候", "工匠", "读书人", "绿林好汉",
                    "文官", "侠客", "商人", "农民", "小吏", "未知","皇帝", "郡王",
                ])
            character_background = st.text_area(
                "角色背景故事（可选）",
                height=100,
                placeholder="描述你的角色的背景、技能和特点..."
            )
            character_info = {
                'name': character_name,
                'gender': character_gender,
                'age': character_age,
                'rank': character_rank,
                'role': f"{character_age}岁{character_gender}，{character_rank}",
                'background': character_background,
                'novel': selected_novel,
                'timeline': selected_timeline,
                'starting_points': 0
            }

        if st.button("开始穿越", type="primary"):
            st.session_state.character_info = character_info
            st.session_state.game_state['character_created'] = True
            st.session_state.game_state['game_started'] = True
            st.session_state.game_state['character_type'] = 'preset' if character_type == "选择已有角色" else 'custom'

            initial_points = character_info.get('starting_points', 20)
            st.session_state.game_state['points'] = initial_points
            st.session_state.game_state['points_history'].append({
                'timestamp': datetime.now(),
                'points': initial_points,
                'change': initial_points
            })

            if character_type == "选择已有角色":
                initial_scene = {
                    "scene_description":  character_info['initial_scene_desc'],
                    "choices": ["开始按原剧情初始发展", "尝试改变剧情走向", "先观察环境", "随缘", "寻找穿越的原因"],
                    "game_update": {"points_awarded": 0, "new_achievement": f"成为{character_info['name']}"}
                }
            else:
                initial_scene = {
                    "scene_description": f"你穿越到了{selected_novel}的{selected_timeline}时期，成为了{character_info['role']}。你需要决定下一步的行动",
                    "choices": ["开始按原剧情初始发展", "尝试改变剧情走向", "先观察环境", "随缘", "寻找穿越的原因"],
                    "game_update": {"points_awarded": 0, "new_achievement": "穿越开始"}
                }

            st.session_state.game_state['current_scene'] = initial_scene
            st.session_state.game_state['scene_history'].append(initial_scene)
            ach = initial_scene['game_update']['new_achievement']
            if ach:
                st.session_state.game_state['achievements'].append(ach)
            st.rerun()

    with col2:
        st.subheader("角色预览")
        if 'character_info' in locals() and character_info:
            st.info("**角色信息预览**")
            st.write(f"**姓名:** {character_info['name']}")
            st.write(f"**性别:** {character_info['gender']}")

            st.write(f"**身份:** {character_info.get('rank')}")
            st.write(f"**世界:** {character_info['novel']}")
            st.write(f"**时间:** {character_info['timeline']}")
            if character_info.get('background'):
                st.write(f"**背景:** {character_info['background']}")
            st.write(f"**初始积分:** {character_info.get('starting_points', 20)}")
            if character_type == "选择已有角色":
                st.success("🎭 经典角色")
            else:
                st.info("✨ 自定义角色")

# 主游戏界面（含流式渲染）
def main_game_interface():
    st.title("🎮 穿越模拟")
    character_info = st.session_state.character_info
    game_state = st.session_state.game_state

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        st.subheader("📜 当前情景")
        character_type = game_state.get('character_type', 'custom')

        novel = character_info['novel']
        if novel == "三国演义":
            img_url = "images/sanguo.png"
        elif novel == "水浒传":
            img_url = "images/shuihu.png"
        elif novel == "明代":
            img_url = "images/mingdai.png"
        elif novel == "清代":
            img_url = "images/hongloumeng.png"
        st.image(img_url, use_container_width=True)

    with col2:
        st.subheader("🎭 游戏进行中")
        character_type = game_state.get('character_type', 'custom')
        if character_type == 'preset':
            st.success(f"你正在扮演经典角色: **{character_info['name']}**")
        else:
            st.info(f"你正在扮演自定义角色: **{character_info['name']}**")

        # === 关键修改：在这里处理“生成中”状态 ===
        if game_state.get('is_generating', False):
            # 显示“AI 正在生成”提示（在剧情位置）
            with st.spinner("⏳ AI 正在生成剧情..."):
                current_scene = game_state['current_scene']
                character_info = st.session_state.character_info
                user_action = st.session_state.get('user_action', '继续探索')

                raw_response = call_llm_api_raw(user_action, current_scene, character_info)
                if raw_response is None:
                    fallback = {
                        "scene_description": f"风云突变！你刚刚选择「{user_action}」，四周气氛骤然紧张...",
                        "choices": ["拔剑应对", "冷静观察", "高声质问", "悄然后退", "寻求盟友"],
                        "game_update": {"points_awarded": 7, "new_achievement": "随机应变"}
                    }
                    new_scene = fallback
                else:
                    new_scene = parse_and_validate_json(raw_response)
                    if new_scene is None:
                        fallback = {
                            "scene_description": f"神秘力量干扰了剧情...你决定：{user_action}",
                            "choices": ["继续前行", "回头看看", "静观其变"],
                            "game_update": {"points_awarded": 5, "new_achievement": "临危不乱"}
                        }
                        new_scene = fallback

                # 流式显示 scene_description
                scene_text = new_scene["scene_description"]
                scene_placeholder = st.empty()
                displayed = ""
                for char in scene_text:
                    displayed += char
                    scene_placeholder.markdown(f"### 📖 剧情发展\n\n{displayed}")
                    time.sleep(0.02)

                # 更新状态
                game_state['current_scene'] = new_scene
                game_state['scene_history'].append(new_scene)
                game_state['choice_history'].append({
                    'timestamp': datetime.now(),
                    'choice': user_action,
                    'points': new_scene['game_update']['points_awarded']
                })
                game_state['points'] += new_scene['game_update']['points_awarded']
                game_state['points_history'].append({
                    'timestamp': datetime.now(),
                    'points': game_state['points'],
                    'change': new_scene['game_update']['points_awarded']
                })
                ach = new_scene['game_update']['new_achievement']
                if ach and ach not in game_state['achievements']:
                    game_state['achievements'].append(ach)

                if 'user_action' in st.session_state:
                    del st.session_state['user_action']
                game_state['is_generating'] = False
                st.rerun()

        else:
            # 正常显示剧情 + 交互
            if game_state['current_scene']:
                current_scene = game_state['current_scene']
                st.markdown("### 📖 剧情发展")
                st.write(current_scene['scene_description'])
                st.markdown("---")
                st.markdown("### 🎯 行动建议")
                choices = current_scene['choices']
                selected_choice = None
                for i, choice in enumerate(choices):
                    if st.button(choice, key=f"choice_{i}", use_container_width=True):
                        selected_choice = choice

                st.markdown("### 💬 自由行动")
                user_input = st.text_input("或者输入自定义行动:", placeholder="描述你想做的任何事情...")
                execute = st.button("执行行动")

                if (selected_choice or (user_input and execute)) and not game_state.get('is_generating', False):
                    user_action = selected_choice or user_input
                    st.session_state.user_action = user_action
                    game_state['is_generating'] = True
                    st.rerun()

    with col3:
        st.subheader("🏆 游戏状态")
        character_type = game_state.get('character_type', 'custom')
        if character_type == 'preset':
            st.markdown("🎭 **经典角色**")
        else:
            st.markdown("✨ **自定义角色**")
        st.metric("积分", game_state['points'])
        st.markdown("### 🏅 成就")
        for a in game_state['achievements']:
            st.success(f"✓ {a}")
        st.markdown("### 📊 游戏统计")
        st.write(f"场景经历: {len(game_state['scene_history'])}")
        st.write(f"选择次数: {len(game_state['choice_history'])}")
        st.write(f"成就数量: {len(game_state['achievements'])}")
        if st.button("重新开始游戏"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# 数据可视化界面
def show_analytics():
    st.header("📈 游戏数据分析")
    game_state = st.session_state.game_state
    if len(game_state['points_history']) > 1:
        df = pd.DataFrame(game_state['points_history'])
        fig_points = go.Figure()
        fig_points.add_trace(go.Scatter(
            x=df['timestamp'], 
            y=df['points'],
            mode='lines+markers',
            name='总积分',
            line=dict(color='#FF4B4B', width=3)
        ))
        fig_points.update_layout(
            title="积分成长趋势",
            xaxis_title="时间",
            yaxis_title="积分",
            template="plotly_white"
        )
        st.plotly_chart(fig_points, use_container_width=True)

        if game_state['choice_history']:
            choices_df = pd.DataFrame(game_state['choice_history'])
            keywords = {
                '战斗': ['攻击', '战斗', '袭击', '拔剑', '迎战'],
                '谈判': ['谈判', '外交', '协商', '交涉', '言和'],
                '侦查': ['侦查', '探索', '观察', '查看', '打听'],
                '准备': ['训练', '准备', '休整', '修炼', '谋划'],
            }
            counts = {}
            total = len(choices_df)
            matched = 0
            for cat, words in keywords.items():
                cnt = sum(1 for c in choices_df['choice'] if any(w in c for w in words))
                counts[cat] = cnt
                matched += cnt
            counts['其他'] = total - matched

            choice_types = pd.DataFrame(list(counts.items()), columns=['type', 'count'])
            # fig_choices = px.pie(
            #     choice_types,
            #     values='count',
            #     names='type',
            #     title="选择类型分布",
            #     color_discrete_sequence=px.colors.qualitative.Set3
            # )
            col1, col2 = st.columns(2)
            # with col1:
            #     st.plotly_chart(fig_choices, use_container_width=True)
            with col1:
                avg_points = game_state['points'] / len(choices_df) if len(choices_df) > 0 else 0
                st.metric("平均每次选择获得积分", f"{avg_points:.1f}")
                efficiency_data = {
                    '指标': ['总积分', '选择次数', '成就数量', '平均效率'],
                    '数值': [game_state['points'], len(choices_df), len(game_state['achievements']), avg_points]
                }
                st.dataframe(efficiency_data, use_container_width=True)

# 角色信息页面
def show_character_info():
    st.header("👤 角色信息")
    character_info = st.session_state.character_info
    game_state = st.session_state.game_state
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("基本信息")
        st.write(f"**姓名:** {character_info['name']}")
        st.write(f"**性别:** {character_info['gender']}")
        st.write(f"**年龄:** {character_info['age']}岁")
        st.write(f"**身份:** {character_info.get('rank')}")
        character_type = game_state.get('character_type', 'custom')
        if character_type == 'preset':
            st.write(f"**角色类型:** 🎭 经典角色")
        else:
            st.write(f"**角色类型:** ✨ 自定义角色")
    with col2:
        st.subheader("穿越信息")
        st.write(f"**世界:** {character_info['novel']}")
        st.write(f"**时间:** {character_info['timeline']}")
        st.write(f"**当前积分:** {game_state['points']}")
        st.write(f"**成就数量:** {len(game_state['achievements'])}")
    if character_info.get('background'):
        st.subheader("背景故事")
        st.write(character_info['background'])
    st.subheader("角色统计数据")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("场景经历", len(game_state['scene_history']))
    with col2:
        st.metric("选择次数", len(game_state['choice_history']))
    with col3:
        # print(game_state['scene_history'])
        points_list = [i["game_update"]["points_awarded"] for i in game_state['scene_history']]
        st.metric("最大的一次积分", max(points_list))

# 主应用
def main():
    initialize_game_state()
    with st.sidebar:
        st.title("🎮 AI穿越模拟")
        st.markdown("---")
        if st.session_state.game_state['character_created']:
            character_info = st.session_state.character_info
            st.success(f"角色: {character_info['name']}")
            character_type = st.session_state.game_state.get('character_type', 'custom')
            if character_type == 'preset':
                st.info(f"类型: 🎭 经典角色")
            else:
                st.info(f"类型: ✨ 自定义角色")
            st.info(f"身份: {character_info.get('rank')}")
            st.info(f"背景: {character_info['novel']} - {character_info['timeline']}")
        st.markdown("---")
        if st.session_state.game_state['character_created']:
            page = st.radio("导航", ["游戏主界面", "数据分析", "角色信息"])
        else:
            page = "角色创建"

    if not st.session_state.game_state['character_created']:
        create_character()

    else:
        if page == "游戏主界面":
            main_game_interface()

        elif page == "数据分析":
            main_game_interface()
            show_analytics()

        elif page == "角色信息":
            show_character_info()


if __name__ == "__main__":
    main()
