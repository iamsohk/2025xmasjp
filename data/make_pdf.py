# -*- coding: utf-8 -*-
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, KeepTogether)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

F = "WQY"
pdfmetrics.registerFont(TTFont(F, "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", subfontIndex=0))

BLACK = colors.HexColor("#18181b")
DARK = colors.HexColor("#27272a")
GREEN = colors.HexColor("#047857")
RED = colors.HexColor("#b91c1c")
AMBER = colors.HexColor("#d97706")
GREYBG = colors.HexColor("#f4f4f5")
BORDER = colors.HexColor("#d4d4d8")

styles = getSampleStyleSheet()
def st(name, size, **kw):
    kw.setdefault("leading", size*1.45)
    return ParagraphStyle(name, fontName=F, fontSize=size, **kw)

s_body = st("body", 9)
s_small = st("small", 7.5, textColor=colors.HexColor("#71717a"))
s_sub = st("sub", 8.5, textColor=colors.HexColor("#555555"))
s_h1 = st("h1", 18, leading=22, textColor=BLACK)
s_li = st("li", 9, leftIndent=10)

doc = SimpleDocTemplate("/home/user/2025xmasjp/data/hk-report.pdf", pagesize=A4,
                        topMargin=1.4*cm, bottomMargin=1.3*cm,
                        leftMargin=1.4*cm, rightMargin=1.4*cm,
                        title="香港供樓利息與租金回報報告 2015-2025")
W = doc.width
E = []

def H2(txt):
    p = Paragraph(txt, st("h2", 12.5, textColor=colors.white))
    t = Table([[p]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),BLACK),
                           ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
                           ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    return t

def box(txt, bar=None, bg="#fafafa", style=None):
    style = style or s_body
    p = Paragraph(txt, style)
    t = Table([[p]], colWidths=[W])
    cmd = [("BACKGROUND",(0,0),(-1,-1),colors.HexColor(bg)),
           ("BOX",(0,0),(-1,-1),1.2,BLACK if not bar else colors.HexColor(bg)),
           ("LEFTPADDING",(0,0),(-1,-1),9),("RIGHTPADDING",(0,0),(-1,-1),9),
           ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]
    if bar:
        cmd.append(("LINEBEFORE",(0,0),(0,-1),4,colors.HexColor(bar)))
    t.setStyle(TableStyle(cmd))
    return t

def data_table(header, rows, colw, special=None):
    data = [header] + rows
    t = Table(data, colWidths=colw, repeatRows=1)
    cmd = [("FONTNAME",(0,0),(-1,-1),F),("FONTSIZE",(0,0),(-1,-1),8),
           ("BACKGROUND",(0,0),(-1,0),DARK),("TEXTCOLOR",(0,0),(-1,0),colors.white),
           ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
           ("GRID",(0,0),(-1,-1),0.5,BORDER),("LINEBELOW",(0,0),(-1,0),0.5,DARK),
           ("TOPPADDING",(0,0),(-1,-1),3.5),("BOTTOMPADDING",(0,0),(-1,-1),3.5),
           ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, GREYBG])]
    if special:
        cmd += special
    t.setStyle(TableStyle(cmd))
    return t

# ---------- Title ----------
E.append(Paragraph("過去 10 年香港供樓利息 × 租金回報 × 樓價", s_h1))
E.append(Table([[None]], colWidths=[W], style=[("LINEBELOW",(0,0),(-1,-1),2.5,BLACK)]))
E.append(Spacer(1,3))
E.append(Paragraph("資料期間 2015–2025　・　整理日期 2026-06-09　・　僅供參考，非投資建議", s_sub))
E.append(Spacer(1,7))
E.append(box('<b>一句總結：</b>歷史數據顯示「<b>租金回報率 &gt; 供樓利息（正息差）</b>」時，樓市約九成時間向上；'
            '但要留意，<b>息差升多數係樓價已跌嘅「結果」</b>，真正推手係<b>利率</b>。'
            '正息差是可靠嘅「抵買／價值區」訊號，而非必升保證。'))

# ---------- Section 1 ----------
E.append(Spacer(1,8)); E.append(H2("一、租金回報率（差餉物業估價署口徑，私人住宅，按面積分類）")); E.append(Spacer(1,2))
E.append(Paragraph("甲A &lt;40㎡　乙B 40–69.9㎡　丙C 70–99.9㎡　丁D 100–159.9㎡　戊E ≥160㎡（細單位回報一般較高）", s_small))
E.append(Spacer(1,3))
yh = ["年份","甲 A","乙 B","丙 C","丁 D","戊 E","備註"]
yrows = [
 ["2015","2.8","2.7","2.6","2.5","2.4","估算"],
 ["2016","2.6","2.5","2.4","2.3","2.2","估算"],
 ["2017","2.4","2.3","2.2","2.1","2.0","估算"],
 ["2018","2.4","2.3","2.2","2.1","2.0","回報見低"],
 ["2019","2.4","2.3","2.2","2.1","2.0",""],
 ["2020","2.3","2.2","2.1","2.0","2.0","疫情"],
 ["2021","2.3","2.2","2.1","2.0","2.0","歷史低位"],
 ["2022","2.4","2.3","2.2","2.0","1.8","甲戊差距 0.6 厘"],
 ["2023","2.9","2.7","2.5","2.3","2.2","樓價回落、回報回升"],
 ["2024","3.4","3.1","2.9","2.6","2.2","甲類為 2012 年來最高"],
 ["2025*","3.3","3.0","2.8","2.6","2.3","*初步"],
]
cw = [1.3,1.1,1.1,1.1,1.1,1.1]
cw = [x*cm for x in cw]; cw.append(W-sum(cw))
E.append(data_table(yh, yrows, cw))

# ---------- Section 2 ----------
E.append(Spacer(1,9)); E.append(H2("二、供樓利率（實際按揭利率）")); E.append(Spacer(1,2))
E.append(Paragraph("P＝滙豐最優惠利率（其他銀行 P 一般高 0.25%）；H按＝1個月 HIBOR + 約1.3%，設封頂息。數值為典型新做按揭有效息概約值。", s_small))
E.append(Spacer(1,3))
mh = ["年份","滙豐 P","1月HIBOR均","H按有效息","P按有效息","H按封頂息","備註"]
mrows = [
 ["2015","5.00","~0.23","~2.05","~2.15","~2.15","超低息年代"],
 ["2016","5.00","~0.40","~1.90","~2.15","~2.15",""],
 ["2017","5.00","~0.55","~1.85","~2.15","~2.35","H+1.3% 成主流"],
 ["2018","5.125","~1.55","~2.375","~2.375","~2.375","9月12年首加P"],
 ["2019","5.00","~1.95","~2.50","~2.50","~2.50","第四季減P"],
 ["2020","5.00","~0.85","~2.00","~2.50","~2.50","疫情、HIBOR回落"],
 ["2021","5.00","~0.13","~1.50","~2.50","~2.50","息率谷底"],
 ["2022","5.625","~1.35","~3.375","~3.375","~3.375","美國加息、HIBOR升"],
 ["2023","5.875","~4.70","~4.125","~4.125","~4.125","利率高峰"],
 ["2024","5.25","~4.40","~3.625","~3.625","~3.625","9月起減息"],
 ["2025*","~5.00","~2.00","~2.625","~3.00","~3.50","*HIBOR年中急跌"],
]
cw2 = [1.25,1.15,1.45,1.45,1.45,1.5]
cw2 = [x*cm for x in cw2]; cw2.append(W-sum(cw2))
E.append(data_table(mh, mrows, cw2))

# ---------- Section 3 ----------
E.append(Spacer(1,9)); E.append(H2("三、核心核對：息差 vs 樓價（你個假設）")); E.append(Spacer(1,2))
E.append(Paragraph("息差 ＝ 租金回報率(甲類A) - H按實際息。樓價為差估署私宅指數年度概約變幅。", s_body))
E.append(Spacer(1,3))
ah = ["年份","租金回報A","H按實際息","息差","樓價按年變幅*","方向吻合"]
arows = [
 ["2015","2.8","2.05","+0.75","+2.4% ↑","○"],
 ["2016","2.6","1.90","+0.70","+7.9% ↑","○"],
 ["2017","2.4","1.85","+0.55","+14.8% ↑","○"],
 ["2018","2.4","2.375","+0.03","+1.6% ↑","○"],
 ["2019","2.4","2.50","-0.10","-0.1% ↓","○"],
 ["2020","2.3","2.00","+0.30","-1.6% ↓","× 疫情例外"],
 ["2021","2.3","1.50","+0.80","+3.4% ↑","○"],
 ["2022","2.4","3.375","-0.98","-15.6% ↓","○"],
 ["2023","2.9","4.125","-1.23","-6.8% ↓","○"],
 ["2024","3.4","3.625","-0.23","-7.1% ↓","○"],
 ["2025*","3.3","2.625","+0.68","~持平/回升","○"],
]
cw3 = [1.4,1.9,1.9,1.6,2.6]
cw3 = [x*cm for x in cw3]; cw3.append(W-sum(cw3))
# color spread col(3) and price col(4) per row
sp = []
for i,r in enumerate(arows, start=1):
    sp.append(("TEXTCOLOR",(3,i),(3,i), GREEN if r[3].startswith("+") else RED))
    sp.append(("FONTNAME",(3,i),(3,i),F))
    sp.append(("TEXTCOLOR",(4,i),(4,i), GREEN if "↑" in r[4] or "回升" in r[4] else RED))
E.append(data_table(ah, arows, cw3, special=sp))
E.append(Spacer(1,2))
E.append(Paragraph("*樓價變幅為差估署私宅指數年度概約值。", s_small))
E.append(Spacer(1,4))
E.append(box('<b>命中率：</b>　正息差年（7次）：6升 1跌（2020疫情例外）→ <b>約 86%</b>；　'
            '負息差年（4次）：4次全跌/持平 → <b>100%</b>；　整體方向吻合度 <b>約 91%（10/11）</b>。<br/>'
            '→ 假設「租金回報 &gt; 供樓利息 ⇒ 樓市傾向升」<b>歷史上大致成立</b>。',
            bar="#047857", bg="#ecfdf5'"[:-1]))

# ---------- Section 4 ----------
E.append(Spacer(1,9)); E.append(H2("四、「最確切原因」：息差多數係「果」，唔係「因」")); E.append(Spacer(1,3))
reasons = ('<b>1. 租金回報 = 租金 ÷ 樓價。</b>回報率升，主要因為<b>樓價已跌</b>（分母縮細），唔係租金暴升。'
 '2023–24 回報跳上 3.4 厘，正正係樓價大跌嘅結果 → 「正息差」通常標示<b>見底／抵買區</b>，唔係保證即刻再升。<br/><br/>'
 '<b>2. 真正共同推手係利率。</b>低息(2015–21)→平錢供樓→樓價升、同時供息低過回報；加息(2022–24)→樓價跌、'
 '同時供息高過回報。<b>樓價同息差都係俾「利率」拖住行</b>，息差只係溫度計。<br/><br/>'
 '<b>3. 正息差≠必升（2020反例）。</b>疫情、移民、供應、信心等宏觀因素一樣會壓樓價。<br/><br/>'
 '<b>實用結論：</b>正息差是可靠嘅「<b>價值／入場區</b>」訊號（下行風險細、現金流轉正、方向命中約九成），'
 '但<b>唔係精準擇時或必升保證</b>。2025 年息差重新轉正，對應「相對抵買、現金流較佳」嘅時間點。')
E.append(box(reasons, bar="#d97706", bg="#fffbeb"))

# ---------- Section 5 ----------
E.append(Spacer(1,9)); E.append(H2("五、官方／權威資料來源（請以此核對精確數字）")); E.append(Spacer(1,3))
src = ('<b>租金回報・樓價（差餉物業估價署 RVD）</b><br/>'
 '・ 物業市場統計資料　www.rvd.gov.hk/tc/publications/property_market_statistics.html<br/>'
 '・ 香港物業報告（年報）　www.rvd.gov.hk/tc/publications/hkpr.html<br/>'
 '・ 開放數據（可下載2015起歷史Excel）　data.gov.hk/tc-data/dataset/hk-rvd-tsinfo_rvd-property-market-statistics<br/><br/>'
 '<b>供樓利率・最優惠利率・HIBOR</b><br/>'
 '・ 政府統計處 港元利率表(340-45021)　www.censtatd.gov.hk/tc/web_table.html?id=340-45021<br/>'
 '・ 滙豐最優惠利率　www.hsbc.com.hk/zh-hk/investments/market-information/hk/lending-rate/<br/>'
 '・ 滙豐 HIBOR 走勢　www.hsbc.com.hk/zh-hk/mortgages/tools/hibor-rate/')
E.append(Paragraph(src, s_body))
E.append(Spacer(1,8))
E.append(Table([[None]], colWidths=[W], style=[("LINEABOVE",(0,0),(-1,-1),0.5,BORDER)]))
E.append(Spacer(1,3))
E.append(Paragraph('數據準確度：本報告由公開資料整理，部分逐年數字為概約值，並以官方公布作錨點校對'
 '（如2024甲類3.4厘為2012年來最高、滙豐P由5%升至5.875%再回落等）。2015–2017逐類租金回報及樓價精確值，'
 '請以上述官方來源為準。本報告僅供參考，並非投資建議。', s_small))

doc.build(E)
print("PDF built OK")
