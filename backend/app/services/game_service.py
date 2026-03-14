import os
import re
import json
from typing import Optional, Dict
from http import HTTPStatus
from dashscope.app import Application
from app.core.config import settings


# 预设角色数据（从原始代码迁移）
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
                    "initial_scene": "你站在东吴大营外，江风凛冽。周瑜刚刚召见你，问：'孔明先生，若用火攻，当如何？'"
                },
                "北伐中原": {
                    "background": "你已六出祁山。但为报先帝之托，仍坚持北伐，帐中烛火彻夜不熄。",
                    "initial_scene": "五丈原秋风萧瑟，你卧于榻上，仍手执羽扇调度军务。姜维入帐急报：'魏军压境！'"
                },
                "三国鼎立": {
                    "background": "蜀汉已立，你坐镇成都，内修政理，外联东吴，时刻警惕曹魏动向。",
                    "initial_scene": "成都丞相府内，你正审阅各地奏章。忽有快马急报：'东吴欲背盟，联络曹魏！'"
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
                    "background": "你镇守江州，威名远播，百姓称颂'一身是胆'。",
                    "initial_scene": "江州城头，你巡视防务。斥候来报：'魏将张郃率军逼近边境！'"
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
                    "initial_scene": "官渡大营中，你召集众将议事。荀彧献计：'明公，当速袭乌巢！'"
                },
                "赤壁之战": {
                    "background": "你率百万大军南下，意图一统江南，但军中疫病流行，水战不利。",
                    "initial_scene": "长江北岸，你眺望对岸联军。程昱谏言：'丞相，东吴有周瑜、诸葛亮，不可轻敌。'"
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
                    "initial_scene": "聚义厅中，你初见林冲、武松等好汉。晁盖举杯道：'今日得公明兄上山，梁山如虎添翼！'"
                },
                "招安之路": {
                    "background": "你力主招安，但兄弟们多有不满，梁山内部暗流涌动。",
                    "initial_scene": "忠义堂内，李逵怒吼：'哥哥若去东京，我便杀尽那帮狗官！'众头领面面相觑。"
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
                    "initial_scene": "南京皇宫中，你批阅奏章，锦衣卫指挥使毛骧跪报：'胡惟庸结党营私，证据确凿！'"
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
                    "initial_scene": "紫禁城乾清宫，你与祖母孝庄太后密谈。太后低语：'玄烨，鳌拜势大，当谨慎行事。'"
                }
            }
        }
    }
}


class GameService:
    """游戏服务"""

    @staticmethod
    def get_preset_character(novel: str, character_name: str, timeline: str) -> Optional[Dict]:
        """获取预设角色信息"""
        if novel not in PRESET_CHARACTERS:
            return None
        if character_name not in PRESET_CHARACTERS[novel]:
            return None

        base_info = PRESET_CHARACTERS[novel][character_name].copy()
        timeline_scenes = base_info.get('timeline_scenes', {})
        timeline_config = timeline_scenes.get(timeline)

        if timeline_config:
            base_info['dynamic_background'] = timeline_config['background']
            base_info['initial_scene_desc'] = timeline_config['initial_scene']
        else:
            base_info['dynamic_background'] = base_info['background']
            base_info['initial_scene_desc'] = f"你穿越到了{novel}的{timeline}时期，成为了{character_name}。{base_info['background']}。你需要决定下一步的行动"

        return base_info

    @staticmethod
    async def call_llm_api(user_input: str, character_info: Dict, session_id: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
        """调用LLM API生成场景

        返回: (响应文本, session_id)
        """
        effective_background = character_info.get('dynamic_background') or character_info.get('background', '无')

        prompt = f"""
        玩家扮演的角色信息如下：
        - 姓名：{character_info['name']}
        - 身份：{character_info['rank']}
        - 背景：{effective_background}
        - 所处世界：{character_info['novel']}
        - 时间节点：{character_info['timeline']}
        玩家做出选择或行动：「{user_input}」
        """.strip()

        # 根据小说选择对应的app_id
        novel = character_info['novel']
        if novel == "三国演义":
            app_id = settings.SANGUO_APP_ID
        elif novel == "水浒传":
            app_id = settings.SHUIHU_APP_ID
        elif novel == "明代":
            app_id = settings.MINGDAI_APP_ID
        elif novel == "清代":
            app_id = settings.QINGDAI_APP_ID
        else:
            return None, session_id

        full_text = ""
        new_session_id = session_id

        try:
            responses = Application.call(
                api_key=settings.DASHSCOPE_API_KEY,
                app_id=app_id,
                prompt=prompt,
                session_id=session_id,
                stream=True,
                incremental_output=True
            )

            for response in responses:
                if response.status_code != HTTPStatus.OK:
                    print(f"LLM调用失败: {response.message} (code={response.status_code})")
                    return None, session_id

                if response.output.text:
                    full_text += response.output.text

                if hasattr(response.output, 'session_id') and response.output.session_id:
                    new_session_id = response.output.session_id

            return full_text, new_session_id

        except Exception as e:
            print(f"调用异常: {e}")
            return None, session_id

    @staticmethod
    def parse_llm_response(raw_text: str) -> Optional[Dict]:
        """解析LLM返回的JSON"""
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
            print(f"JSON解析失败: {e}")
            return None

    @staticmethod
    def get_fallback_scene(user_action: str) -> Dict:
        """获取备用场景"""
        return {
            "scene_description": f"风云突变！你刚刚选择「{user_action}」，四周气氛骤然紧张...",
            "choices": ["拔剑应对", "冷静观察", "高声质问", "悄然后退", "寻求盟友"],
            "game_update": {"points_awarded": 7, "new_achievement": "随机应变"}
        }
