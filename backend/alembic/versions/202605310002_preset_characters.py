"""preset characters tables with seed data

Revision ID: 202605310002
Revises: 202605310001
Create Date: 2026-05-31 11:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "202605310002"
down_revision = "202605310001"
branch_labels = None
depends_on = None


PRESET_SEED = [
    # (novel, name, gender, age, rank, background, starting_points, timelines)
    # timelines: [(timeline, bg, initial_scene), ...]
    ("三国演义", "诸葛亮", "男性", 35, "军师",
     "字孔明，号卧龙，琅琊阳都人。三国时期蜀汉丞相，杰出的政治家、军事家、文学家。", 60,
     [("赤壁之战", "你正于东吴舌战群儒，力主孙刘联盟。周瑜对你又敬又忌，而你心中已有火攻之计。",
       "你站在东吴大营外，江风凛冽。周瑜刚刚召见你，问：'孔明先生，若用火攻，当如何？'"),
      ("北伐中原", "你已六出祁山。但为报先帝之托，仍坚持北伐，帐中烛火彻夜不熄。",
       "五丈原秋风萧瑟，你卧于榻上，仍手执羽扇调度军务。姜维入帐急报：'魏军压境！'"),
      ("三国鼎立", "蜀汉已立，你坐镇成都，内修政理，外联东吴，时刻警惕曹魏动向。",
       "成都丞相府内，你正审阅各地奏章。忽有快马急报：'东吴欲背盟，联络曹魏！'")]),
    ("三国演义", "赵云", "男性", 32, "将军",
     "字子龙，常山真定人。身长八尺，姿颜雄伟，蜀汉名将，以忠勇著称。", 45,
     [("赤壁之战", "你随刘备驻扎夏口，虽未直接参战，但已展现出非凡胆略。",
       "夏口江边，你奉命护送刘备家眷。远处赤壁火光冲天，喊杀声震耳欲聋。"),
      ("三国鼎立", "你镇守江州，威名远播，百姓称颂'一身是胆'。",
       "江州城头，你巡视防务。斥候来报：'魏将张郃率军逼近边境！'")]),
    ("三国演义", "曹操", "男性", 40, "丞相",
     "字孟德，小字阿瞒，沛国谯县人。东汉末年杰出政治家、军事家、文学家。魏武帝", 65,
     [("官渡之战", "你与袁绍对峙于官渡，粮草将尽，但已定下奇袭乌巢之计。",
       "官渡大营中，你召集众将议事。荀彧献计：'明公，当速袭乌巢！'"),
      ("赤壁之战", "你率百万大军南下，意图一统江南，但军中疫病流行，水战不利。",
       "长江北岸，你眺望对岸联军。程昱谏言：'丞相，东吴有周瑜、诸葛亮，不可轻敌。'")]),

    ("水浒传", "宋江", "男性", 38, "小吏",
     "字公明，绰号呼保义、及时雨，梁山一百单八将之首。", 55,
     [("梁山聚义", "你刚上梁山，晁盖尚在，众好汉对你既敬且疑。",
       "聚义厅中，你初见林冲、武松等好汉。晁盖举杯道：'今日得公明兄上山，梁山如虎添翼！'"),
      ("招安之路", "你力主招安，但兄弟们多有不满，梁山内部暗流涌动。",
       "忠义堂内，李逵怒吼：'哥哥若去东京，我便杀尽那帮狗官！'众头领面面相觑。")]),
    ("水浒传", "武松", "男性", 28, "步军头领",
     "绰号行者，又称武二郎，景阳冈打虎英雄，勇猛刚烈，义薄云天。", 46,
     [("梁山聚义", "你刚上梁山，因打虎、杀西门庆之名，备受敬重。",
       "你站在沙滩上，望着浩渺水泊。鲁智深拍你肩膀：'兄弟，今后咱们并肩作战！'"),
      ("攻打祝家庄", "你随军攻打祝家庄，展现勇武，但心中对梁山前途有所疑虑。",
       "祝家庄外，你手持戒刀，准备冲锋。宋江下令：'武松兄弟，你带一队人马从东门杀入！'")]),
    ("水浒传", "林冲", "男性", 35, "马军头领",
     "绰号豹子头，原为东京八十万禁军教头，武艺高强，上梁山。", 50,
     [("梁山聚义", "你已被逼上梁山，但心中对朝廷仍有眷恋，郁郁寡欢。",
       "梁山泊中，你独自练枪。晁盖走来道：'林教头，今日我等替天行道，何不畅饮？'"),
      ("招安之路", "你对招安持保留态度，经历官场，深知朝廷腐败。",
       "忠义堂内，当宋江提出招安，你沉默不语，手中酒杯微微颤抖。")]),

    ("明代", "朱元璋", "男性", 40, "皇帝",
     "明朝开国皇帝，年号洪武，布衣出身，建立大明王朝。", 70,
     [("洪武之治", "你已登基为帝，大力反腐，整顿吏治，但诛杀功臣，朝中人心惶惶。",
       "南京皇宫中，你批阅奏章，锦衣卫指挥使毛骧跪报：'胡惟庸结党营私，证据确凿！'")]),
    ("明代", "朱棣", "男性", 35, "燕王/皇帝",
     "明成祖，朱元璋第四子，原为燕王，通过靖难之役夺取皇位，年号永乐。", 65,
     [("靖难之役", "你以清君侧为名，起兵反抗建文帝，战事胶着。",
       "北平燕王府，你召集姚广孝等谋士。道衍和尚说：'殿下，当速取南京！'"),
      ("永乐盛世", "你已登基，迁都北京，派郑和下西洋，修《永乐大典》，国力强盛。",
       "北京紫禁城中，你接见郑和：'三宝，此次下西洋，当扬我国威！'")]),
    ("明代", "张居正", "男性", 45, "首辅",
     "字叔大，明代杰出政治家，推行万历新政，改革赋税。", 60,
     [("万历乱局", "你作为首辅，大力改革，但权倾朝野，引来朝中非议。",
       "文渊阁中，你审阅考成法奏章。小皇帝万历在一旁读书，太后垂帘听政。")]),

    ("清代", "康熙", "男性", 20, "皇帝",
     "爱新觉罗·玄烨，清朝第四位皇帝，年号康熙，开创康乾盛世。", 70,
     [("康熙继位", "你年幼登基，权臣鳌拜专权，你暗中积蓄力量。",
       "紫禁城乾清宫，你与祖母孝庄太后密谈。太后低语：'玄烨，鳌拜势大，当谨慎行事。'"),
      ("九子夺嫡", "你年事已高，诸皇子争夺储位，朝局动荡。",
       "畅春园中，你卧病在床，听闻胤禩、胤禛等皇子结党营私，心中忧愤。")]),
    ("清代", "林则徐", "男性", 50, "钦差大臣",
     "字元抚，清代政治家、思想家，虎门销烟主持者。", 55,
     [("虎门销烟", "你奉命赴广东禁烟，面对英商狡诈和朝廷压力，毅然销毁大烟。",
       "虎门海滩，你下令销毁大烟。洋商抗议，你厉声道：'大烟流毒，害我中华！'")]),
    ("清代", "李鸿章", "男性", 60, "直隶总督",
     "字渐甫，号少荃，晚清重臣，洋务运动主要领导人，北洋水师创建者。", 60,
     [("洋务运动", "你大力推行洋务，创办江南制造局、轮船招商局等，以求自强。",
       "天津直隶总督府，你与盛宣怀商议：'当兴办铁路、电报，以固国本。'"),
      ("甲午战争", "朝鲜东学党起事，你派军赴朝，日本趁机出兵，战事一触即发。",
       "朝鲜动乱，你派军前往朝鲜平叛。北洋水师提督丁汝昌急电：'日舰已在黄海游弋！'")]),
]


def upgrade():
    op.create_table(
        "preset_characters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("novel", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("gender", sa.String(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("rank", sa.String(), nullable=True),
        sa.Column("background", sa.Text(), nullable=True),
        sa.Column("starting_points", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_preset_characters_id"), "preset_characters", ["id"], unique=False)
    op.create_index(op.f("ix_preset_characters_novel"), "preset_characters", ["novel"], unique=False)

    op.create_table(
        "character_timelines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("timeline", sa.String(), nullable=False),
        sa.Column("background", sa.Text(), nullable=True),
        sa.Column("initial_scene", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["preset_characters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_character_timelines_id"), "character_timelines", ["id"], unique=False)

    # Seed data — use raw SQL with RETURNING for PostgreSQL
    conn = op.get_bind()
    for novel, name, gender, age, rank, bg, pts, timelines in PRESET_SEED:
        row = conn.execute(
            sa.text(
                "INSERT INTO preset_characters (novel, name, gender, age, rank, background, starting_points) "
                "VALUES (:novel, :name, :gender, :age, :rank, :bg, :pts) RETURNING id"
            ),
            {"novel": novel, "name": name, "gender": gender, "age": age, "rank": rank, "bg": bg, "pts": pts}
        ).fetchone()
        char_id = row[0]
        for tl, tl_bg, tl_scene in timelines:
            conn.execute(
                sa.text(
                    "INSERT INTO character_timelines (character_id, timeline, background, initial_scene) "
                    "VALUES (:cid, :tl, :bg, :scene)"
                ),
                {"cid": char_id, "tl": tl, "bg": tl_bg, "scene": tl_scene}
            )


def downgrade():
    op.drop_index(op.f("ix_character_timelines_id"), table_name="character_timelines")
    op.drop_table("character_timelines")
    op.drop_index(op.f("ix_preset_characters_novel"), table_name="preset_characters")
    op.drop_index(op.f("ix_preset_characters_id"), table_name="preset_characters")
    op.drop_table("preset_characters")
