"""create novel_configs and timeline_configs tables with seed data

Revision ID: 202606220001
Revises: 202606140002
Create Date: 2026-06-22 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "202606220001"
down_revision = "202606140002"
branch_labels = None
depends_on = None

# 种子数据：小说
NOVEL_SEEDS = [
    {"name": "三国演义", "description": "东汉末年，群雄并起", "sort_order": 1},
    {"name": "水浒传", "description": "官逼民反，梁山聚义", "sort_order": 2},
    {"name": "明代", "description": "大明王朝的兴衰", "sort_order": 3},
    {"name": "清代", "description": "从入关到末路", "sort_order": 4},
    {"name": "西游记", "description": "西天取经，妖魔横行", "sort_order": 5},
]

# 种子数据：时间节点 (novel_name, timeline_name, sort_order, description)
TIMELINE_SEEDS = [
    # 三国演义
    ("三国演义", "黄巾起义", 1, "汉末大乱之始"),
    ("三国演义", "董卓乱政", 2, "西凉铁骑入京"),
    ("三国演义", "官渡之战", 3, "曹操 vs 袁绍"),
    ("三国演义", "赤壁之战", 4, "孙刘联军破曹"),
    ("三国演义", "三国鼎立", 5, "天下三分"),
    ("三国演义", "北伐中原", 6, "诸葛亮六出祁山"),
    # 水浒传
    ("水浒传", "洪太尉访道", 1, "伏魔殿开启"),
    ("水浒传", "梁山聚义", 2, "一百单八将齐聚"),
    ("水浒传", "攻打祝家庄", 3, "三打祝家庄"),
    ("水浒传", "招安之路", 4, "接受朝廷招安"),
    ("水浒传", "征讨方腊", 5, "南征方腊"),
    ("水浒传", "卸甲还乡", 6, "英雄归隐"),
    # 明代
    ("明代", "洪武之治", 1, "朱元璋开国"),
    ("明代", "靖难之役", 2, "朱棣夺位"),
    ("明代", "永乐盛世", 3, "郑和下西洋"),
    ("明代", "土木堡之变", 4, "明英宗被俘"),
    ("明代", "万历乱局", 5, "张居正改革后"),
    ("明代", "女真崛起", 6, "努尔哈赤崛起"),
    ("明代", "闯王进京", 7, "李自成破北京"),
    # 清代
    ("清代", "八旗入关", 1, "清军入主中原"),
    ("清代", "康熙继位", 2, "少年天子"),
    ("清代", "九子夺嫡", 3, "皇位之争"),
    ("清代", "马戛尔尼访华", 4, "东西方碰撞"),
    ("清代", "虎门销烟", 5, "林则徐禁烟"),
    ("清代", "金田起义", 6, "太平天国兴起"),
    ("清代", "第二次中英战争", 7, "英法联军"),
    ("清代", "洋务运动", 8, "师夷长技"),
    ("清代", "甲午战争", 9, "中日海战"),
    ("清代", "八国联军进京", 10, "庚子事变"),
    ("清代", "预备立宪", 11, "末路改革"),
    # 西游记
    ("西游记", "大闹天宫", 1, "齐天大圣"),
    ("西游记", "五行山下", 2, "五百年等待"),
    ("西游记", "西天取经", 3, "踏上取经路"),
    ("西游记", "三打白骨精", 4, "妖魔惑众"),
    ("西游记", "女儿国", 5, "情关难渡"),
    ("西游记", "真假美猴王", 6, "六耳猕猴"),
    ("西游记", "火焰山", 7, "三借芭蕉扇"),
    ("西游记", "取得真经", 8, "功德圆满"),
]

# 使用元数据反射而非直接引用 ORM 模型
novel_configs = sa.Table(
    "novel_configs",
    sa.MetaData(),
    sa.Column("id", sa.Integer),
    sa.Column("name", sa.String),
    sa.Column("description", sa.Text),
    sa.Column("sort_order", sa.Integer),
    sa.Column("created_at", sa.DateTime),
)

timeline_configs = sa.Table(
    "timeline_configs",
    sa.MetaData(),
    sa.Column("id", sa.Integer),
    sa.Column("novel_id", sa.Integer),
    sa.Column("name", sa.String),
    sa.Column("description", sa.Text),
    sa.Column("sort_order", sa.Integer),
    sa.Column("created_at", sa.DateTime),
)


def upgrade():
    # ── 创建 novel_configs 表 ──
    op.create_table(
        "novel_configs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 创建 timeline_configs 表 ──
    op.create_table(
        "timeline_configs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novel_configs.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 种子数据 ──
    conn = op.get_bind()

    # 逐条插入小说
    for n in NOVEL_SEEDS:
        existing = conn.execute(
            novel_configs.select().where(novel_configs.c.name == n["name"])
        ).first()
        if not existing:
            conn.execute(
                novel_configs.insert().values(
                    name=n["name"],
                    description=n["description"],
                    sort_order=n["sort_order"],
                )
            )

    # 逐条插入时间节点
    for novel_name, tl_name, sort_order, desc in TIMELINE_SEEDS:
        # 查询 novel_id
        novel_row = conn.execute(
            novel_configs.select().where(novel_configs.c.name == novel_name)
        ).first()
        if novel_row is None:
            continue

        existing = conn.execute(
            timeline_configs.select().where(
                timeline_configs.c.novel_id == novel_row.id,
                timeline_configs.c.name == tl_name,
            )
        ).first()
        if not existing:
            conn.execute(
                timeline_configs.insert().values(
                    novel_id=novel_row.id,
                    name=tl_name,
                    description=desc,
                    sort_order=sort_order,
                )
            )


def downgrade():
    op.drop_table("timeline_configs")
    op.drop_table("novel_configs")
