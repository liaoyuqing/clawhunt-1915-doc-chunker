"""生成 3 个虚构样例文档（samples/doc_1..3.json）。

全部内容为虚构数据，不含任何真实企业名、真实人名。
执行：python scripts/make_samples.py
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SAMPLES = os.path.join(ROOT, "samples")


# ---------- 句库（虚构） ----------

BOOKING = [
    "会员企业可在每个自然月第一个工作日的上午九点起提交下个月的会议室预定申请。",
    "预定系统按提交时间先后排序，同一时段同一房间只保留一条有效记录。",
    "预定成功后申请人会收到一条站内消息，消息里带有房间编号与当次入场码。",
    "房间编号规则为楼栋字母加两位楼层数字，再追加两位房间序号，例如 A0321。",
    "大型路演厅需要提前十个工作日申请，并在申请里附上活动说明与预计到场人数。",
    "预定人可以在会议开始前四小时内自助修改时段，修改后仍按原提交顺序保留位置。",
    "超过预定开始时间二十分钟仍无人入场，系统会自动释放房间并通知候补队列。",
    "若同一企业在三十天内累计三次未按时入场，系统会暂停其预定权限七个自然日。",
]

CANCEL = [
    "取消预定需要在会议开始时间两小时之前完成，否则计为一次未到场记录。",
    "连续两次未到场会触发站内提醒，提醒后仍不取消的，按次数累计计入月度报告。",
    "因场地检修或设备故障导致的取消由运营方发起，不计入企业名下的记录。",
    "企业可以在月度报告发出后的五个工作日内对异常记录提出复核申请。",
]

CROSSPAGE = [
    "跨页说明用于记录那些在纸质版面上被分页、但在语义上属于同一段的规则。",
    "这类段落在解析阶段会带上起始页与结束页两个页码，切片时需要同时保留。",
    "样例中这一段起于第三页末尾，续于第四页开头，专门用于校验页码字段。",
]

DESK = [
    "服务台负责受理会员企业的日常咨询，工作时间为每个工作日的九点到十八点。",
    "咨询分为场地、结算、系统三个类别，受理后按类别分派到对应的小组处理。",
    "紧急事项可以直接拨打内线，接线记录会自动同步到当日的工单列表里。",
    "服务台不代办跨企业的资源对接，此类需求请走资源大厅的对接入口提交。",
]

DUTY = [
    "值班安排按周轮换，每周由一名值班经理与两名协助人员共同组成。",
    "值班经理负责当日全部工单的分派与超时提醒。",
]

FEE = [
    "费用与结算模块记录会员企业的场地使用与增值服务支出明细。",
    "所有金额以分为单位存储为整数，展示时再统一换算为元并保留两位小数。",
    "月度账单在每个自然月结束后的第三个工作日生成并推送给企业管理员。",
    "账单生成后进入五个工作日的核对期，核对期内可以提出异议并附上凭据。",
]

NOTICE = [
    "临时公告用于发布当日的场地变动与临时闭馆安排。",
]

TOUR = [
    "园区导览介绍公共区域的开放时间、参观动线与讲解服务的预约方式。",
    "参观者需要在前台登记并领取一张临时通行卡，离场时交回。",
    "导览路线全长约八百米，正常步速下的参观时间约为二十五分钟。",
    "团体参观需要提前三个工作日预约讲解员，并告知参观人数与关注方向。",
]

EXPO = [
    "展厅分为常设展区与轮换展区，常设展区全年开放，轮换展区每季度更换一次。",
    "参观预约按半小时划分为一个时段，每个时段限额四十人，约满为止。",
    "预约成功后凭临时通行卡入场，无需在现场再次登记个人信息。",
    "展厅内禁止饮食，拍摄需要提前告知现场人员并遵守展品标注的要求。",
]

GUIDE = [
    "讲解服务分为固定场次与预约场次两类，两类场次都从展厅入口集合出发。",
    "固定场次在每天上午十点与下午三点各开一场，无需单独预约。",
    "预约场次需要至少十人成团，讲解时长约四十分钟，路线覆盖三个常设展区。",
]

EMERG = [
    "遇到设备故障或人身不适，请立即联系服务台或按下现场呼叫按钮。",
    "现场配有应急药箱与自动体外除颤设备，位置在展厅东侧服务点。",
    "疏散通道位于展厅东西两侧，通道内不得堆放任何物品。",
]

METRO = [
    "地铁接驳专线在早晚高峰每十五分钟一班，平峰时段每三十分钟一班。",
    "专线停靠东门与南门两站，单程约八分钟，刷通行卡免费乘坐。",
    "末班车在晚间九点从东门发车，节假日的班次以当日公告为准。",
]

APPENDIX = [
    "附录说明汇总术语口径与字段含义，便于检索时对照原文。",
    "术语按拼音顺序排列，每条给出一句释义并标注适用范围。",
    "字段含义与知识库检索页面展示的字段保持一致，便于交叉核对。",
]

LONG3 = [
    "这段文字用于校验跨越三页的超长段落，段落本身显著长于单片的长度上限。",
    "解析阶段会给出该段的起始页与结束页，切片时需要保证页码区间连续。",
    "若某一片只覆盖段落的一部分，页码范围按覆盖比例在起止页之间取值。",
    "相邻切片的页码范围不应出现空洞，后一片的起始页不晚于前一片的结束页。",
    "第一片的起始页应当等于段落的起始页，最后一片的结束页应当等于段落的结束页。",
]

SHORT = [
    "本节内容很短，用于校验短切片只来自短小节这一条规则。",
]


def fill(pool, target: int) -> str:
    """从句库循环取句，拼到不少于 target 个字符为止。"""
    out = []
    total = 0
    index = 0
    while total < target:
        sentence = pool[index % len(pool)]
        out.append(sentence)
        total += len(sentence)
        index += 1
    return "".join(out)


def table(header, rows, seq: int, page: int) -> dict:
    return {"seq": seq, "type": "table", "page": page, "rows": [header] + rows}


def build_doc_1() -> dict:
    """样例一：四层标题栈、跨页段落、整表与拆表、短小节。"""
    blocks: list = []
    counter = [0]

    def add(block: dict) -> None:
        block.setdefault("seq", counter[0])
        counter[0] += 1
        blocks.append(block)

    add({"type": "heading", "text": "空间与服务", "level": 1})
    add({"type": "heading", "text": "会议室", "level": 2})
    add({"type": "heading", "text": "预订规则", "level": 3})
    add({"type": "paragraph", "page": 3, "text": fill(BOOKING, 900)})
    add({"type": "paragraph", "page": 3, "text": fill(BOOKING[3:], 780)})
    add({"type": "heading", "text": "取消规则", "level": 3})
    add({"type": "paragraph", "page": 4, "text": fill(CANCEL, 520)})
    add({"type": "heading", "text": "跨页说明", "level": 3})
    add({"type": "paragraph", "page_start": 3, "page_end": 4, "text": fill(CROSSPAGE, 170)})
    add({"type": "heading", "text": "服务台", "level": 2})
    add({"type": "paragraph", "page": 5, "text": fill(DESK, 860)})
    add({"type": "paragraph", "page": 5, "text": fill(DESK[2:], 420)})
    add({"type": "heading", "text": "值班安排", "level": 3})
    add({"type": "paragraph", "page": 5, "text": fill(DUTY, 120)})
    add({"type": "heading", "text": "费用与结算", "level": 2})
    add({"type": "paragraph", "page": 6, "text": fill(FEE, 610)})
    add({"type": "heading", "text": "结算标准", "level": 3})
    whole_rows = [
        ["A01", "场地使用", "按小时计费，不足一小时的部分按一小时计", "样例"],
        ["A02", "设备借用", "投影与音响免费，同声传译设备按场次另计", "样例"],
        ["A03", "增值服务", "茶歇与场地布置按场次计费，不含额外人工", "样例"],
        ["A04", "超时使用", "超过预定结束时间半小时起开始计费", "样例"],
        ["A05", "取消损失", "开始前两小时内取消按半场计费", "样例"],
        ["A06", "跨区调场", "需要提前两个工作日提交申请并说明原因", "样例"],
        ["A07", "发票开具", "账单核对期结束后统一开具，纸质邮寄另计", "样例"],
        ["A08", "对账口径", "以系统记录为准，人工登记不参与对账", "样例"],
        ["A09", "候补释放", "房间释放后候补队列按排队顺序自动补位", "样例"],
        ["A10", "权限暂停", "三十天内三次未到场暂停预定权限七个自然日", "样例"],
        ["A11", "调整时段", "开始前四小时内可自助调整，排序位置不变", "样例"],
        ["A12", "路演申请", "大型路演厅需提前十个工作日提交活动说明", "样例"],
        ["A13", "押金退还", "活动结束后五个工作日内原路退还押金", "样例"],
        ["A14", "损坏赔付", "按维修报价单金额赔付，报价单随账单送达", "样例"],
        ["A15", "能耗分摊", "公共区域能耗按使用面积在会员企业间分摊", "样例"],
        ["A16", "账期约定", "账期以合同约定为准，默认三十个自然日", "样例"],
        ["A17", "异议处理", "核对期内提出异议的，账单冻结至处理完毕", "样例"],
        ["A18", "凭证留存", "电子凭证在系统中留存三个自然年备查", "样例"],
        ["A19", "临时闭馆", "临时闭馆由运营方公告，已产生的预定顺延", "样例"],
        ["A20", "设备报修", "设备报修在四小时内响应，隔日完成更换", "样例"],
        ["A21", "入场核验", "入场码由系统生成，一人一码不得转借", "样例"],
        ["A22", "候补排队", "候补队列按提交时间排序，释放后十分钟内确认", "样例"],
        ["A23", "跨月账单", "跨月使用的费用按实际使用日期分月计入", "样例"],
        ["A24", "优惠抵扣", "优惠券在账单生成时自动抵扣，不与其他优惠叠加", "样例"],
        ["A25", "滞纳处理", "账期结束后十个自然日未结清计入滞纳提醒", "样例"],
        ["A26", "数据导出", "企业管理员可导出近十二个月的使用明细", "样例"],
        ["A27", "变更通知", "计费口径变更提前三十个自然日公告", "样例"],
        ["A28", "争议升级", "争议未在核对期内解决的升级至运营负责人", "样例"],
    ]
    add(table(["编号", "项目", "计费说明", "备注"], whole_rows, counter[0], 6))
    add({"type": "heading", "text": "临时公告", "level": 3})
    add({"type": "paragraph", "page": 6, "text": "".join(SHORT)})
    add({"type": "heading", "text": "闭馆提醒", "level": 3})
    add({"type": "paragraph", "page": 6, "text": "闭馆安排以当周公告为准，请提前安排行程以免影响使用。"})
    add({"type": "heading", "text": "明细清单", "level": 3})
    detail_rows = []
    kinds = ["场地", "设备", "服务", "其他"]
    for index in range(1, 41):
        detail_rows.append([
            "R%02d" % index,
            kinds[index % len(kinds)],
            "明细条目第 %02d 项，用于校验拆表后每片都带表头且数据行不重不漏。" % index,
            "第%d行" % index,
        ])
    add(table(["序号", "类型", "说明", "标记"], detail_rows, counter[0], 6))
    add({"type": "footer", "text": "第 6 页"})
    return {
        "version_id": "doc-1",
        "title": "会员空间知识库样例一（标题栈、跨页、整表与拆表）",
        "blocks": blocks,
    }


def build_doc_2() -> dict:
    """样例二：三级嵌套与跳级标题、兄弟标题不污染、真实长度的正文。"""
    blocks: list = []
    counter = [0]

    def add(block: dict) -> None:
        block.setdefault("seq", counter[0])
        counter[0] += 1
        blocks.append(block)

    add({"type": "heading", "text": "园区导览", "level": 1})
    add({"type": "paragraph", "page": 1, "text": fill(TOUR, 700)})
    add({"type": "heading", "text": "展厅与动线", "level": 2})
    add({"type": "heading", "text": "参观预约", "level": 3})
    add({"type": "paragraph", "page": 2, "text": fill(EXPO, 820)})
    add({"type": "heading", "text": "讲解服务", "level": 3})
    add({"type": "paragraph", "page": 2, "text": fill(GUIDE, 660)})
    add({"type": "heading", "text": "服务台", "level": 2})
    add({"type": "paragraph", "page": 3, "text": fill(DESK, 640)})
    add({"type": "heading", "text": "应急联络", "level": 3})
    add({"type": "paragraph", "page": 3, "text": fill(EMERG, 520)})
    add({"type": "heading", "text": "交通指引", "level": 1})
    add({"type": "heading", "text": "地铁接驳", "level": 3})
    add({"type": "paragraph", "page": 4, "text": fill(METRO, 680)})
    return {
        "version_id": "doc-2",
        "title": "会员空间知识库样例二（三级嵌套与跳级）",
        "blocks": blocks,
    }


def build_doc_3() -> dict:
    """样例三：跨三页超长段落、文档以三级标题开头、短小节、小表。"""
    blocks: list = []
    counter = [0]

    def add(block: dict) -> None:
        block.setdefault("seq", counter[0])
        counter[0] += 1
        blocks.append(block)

    add({"type": "heading", "text": "附录说明", "level": 3})
    add({"type": "paragraph", "page": 1, "text": fill(APPENDIX, 640)})
    add({"type": "heading", "text": "数据附录", "level": 2})
    add({"type": "paragraph", "page": 2, "text": fill(APPENDIX[1:], 560)})
    appendix_rows = [
        ["T01", "切片", "按标题结构切分后的文本单元，可带重叠", "样例"],
        ["T02", "标题路径", "从一级标题到当前小节的标题数组，逐级下沉", "样例"],
        ["T03", "页码区间", "切片覆盖的起始页与结束页，跨页时两值不同", "样例"],
        ["T04", "整表切片", "未拆分的表格整体成片，允许超过长度上限", "样例"],
        ["T05", "表头重复", "拆表后每一片的首行都重复原表头", "样例"],
        ["T06", "短小节", "原小节本身不足下限时允许单独成片", "样例"],
        ["T07", "重叠字数", "同一小节内相邻切片共享的字符数", "样例"],
        ["T08", "来源块号", "切片覆盖的解析阶段块序号，从零开始", "样例"],
    ]
    add(table(["术语编号", "术语", "释义", "备注"], appendix_rows, counter[0], 2))
    add({"type": "heading", "text": "三页长文", "level": 1})
    add({"type": "paragraph", "page_start": 3, "page_end": 5, "text": fill(LONG3, 1760)})
    add({"type": "heading", "text": "短小节示例", "level": 2})
    add({"type": "paragraph", "page": 5, "text": "".join(SHORT)})
    return {
        "version_id": "doc-3",
        "title": "会员空间知识库样例三（跨三页与短小节）",
        "blocks": blocks,
    }


def main() -> int:
    os.makedirs(SAMPLES, exist_ok=True)
    docs = [
        ("doc_1.json", build_doc_1()),
        ("doc_2.json", build_doc_2()),
        ("doc_3.json", build_doc_3()),
    ]
    for name, doc in docs:
        path = os.path.join(SAMPLES, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print("wrote %s (%d blocks)" % (path, len(doc["blocks"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())