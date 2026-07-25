import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ============ 页面设置 ============
st.set_page_config(page_title="RFM 客户价值模型", layout="wide", page_icon="📊")
st.title("📊 RFM 客户价值分析看板")
st.caption("基于 R（最近购买）· F（购买频率）· M（消费金额） 三维度进行客户分群")

# ============ 读取数据 ============
@st.cache_data
def load_data():
    df = pd.read_excel("D:\赵祎琳大信球\1\streamlit练习\原始sales.xlsx")
    df["提交日期"] = pd.to_datetime(df["提交日期"])
    return df

df = load_data()

# ============ 计算 RFM ============
# @st.cache_data
def compute_rfm(df, reference_date):
    rfm = df.groupby("会员ID").agg(
        最近购买日期=("提交日期", "max"),
        购买次数=("订单号", "nunique"),
        累计消费=("订单金额", "sum"),
        平均客单价=("订单金额", "mean"),
        首次购买=("提交日期", "min"),
    ).reset_index()

    rfm["R_天数"] = (reference_date - rfm["最近购买日期"]).dt.days
    rfm["客户生命周期"] = (rfm["最近购买日期"] - rfm["首次购买"]).dt.days

    return rfm

# 以数据最大日期的次日为参考日
reference_date = df["提交日期"].max() + pd.Timedelta(days=1)
rfm = compute_rfm(df, reference_date)

# ============ RFM 评分 ============
def rfm_score(rfm):
    """按分位数打分 1-5，5 最优"""
    df = rfm.copy()

    # R 越小越好，所以反向打分
    df["R_评分"] = pd.qcut(df["R_天数"], q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    # F 越大越好
    df["F_评分"] = pd.qcut(df["购买次数"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    # M 越大越好
    df["M_评分"] = pd.qcut(df["累计消费"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]).astype(int)

    df["RFM_总分"] = df["R_评分"] + df["F_评分"] + df["M_评分"]
    return df

rfm_scored = rfm_score(rfm)

# ============ 客户分群 ============
def segment_customer(row):
    r, f, m = row["R_评分"], row["F_评分"], row["M_评分"]

    if r >= 4 and f >= 4 and m >= 4:
        return "🏆 重要价值客户"
    elif r >= 4 and f >= 4 and m < 4:
        return "🔄 重要保持客户"
    elif r >= 4 and f < 4 and m >= 4:
        return "💎 重要发展客户"
    elif r < 4 and f >= 4 and m >= 4:
        return "⚠️ 重要挽留客户"
    elif r >= 4 and f < 4 and m < 4:
        return "🌱 新客户"
    elif r < 4 and f >= 4 and m < 4:
        return "😴 一般保持客户"
    elif r < 4 and f < 4 and m >= 4:
        return "💤 一般挽留客户"
    else:
        return "❄️ 流失客户"

rfm_scored["客户分群"] = rfm_scored.apply(segment_customer, axis=1)

# ============ 侧边栏 ============
st.sidebar.header("筛选条件")

# 客户分群筛选
segments = rfm_scored["客户分群"].unique().tolist()
selected_segments = st.sidebar.multiselect("客户分群", segments, default=segments)

# R 评分筛选
r_range = st.sidebar.slider("R 评分（最近购买）", 1, 5, (1, 5))
f_range = st.sidebar.slider("F 评分（购买频率）", 1, 5, (1, 5))
m_range = st.sidebar.slider("M 评分（消费金额）", 1, 5, (1, 5))

# 筛选数据
mask = (
    (rfm_scored["客户分群"].isin(selected_segments)) &
    (rfm_scored["R_评分"].between(r_range[0], r_range[1])) &
    (rfm_scored["F_评分"].between(f_range[0], f_range[1])) &
    (rfm_scored["M_评分"].between(m_range[0], m_range[1]))
)
filtered = rfm_scored[mask]

# ============ 顶部 KPI ============
st.subheader("📈 整体概览")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("客户总数", f"{len(filtered):,}")
k2.metric("平均 R（天）", f"{filtered['R_天数'].mean():.0f}")
k3.metric("平均 F（次）", f"{filtered['购买次数'].mean():.1f}")
k4.metric("平均 M（元）", f"¥{filtered['累计消费'].mean():,.0f}")
k5.metric("平均客单价", f"¥{filtered['平均客单价'].mean():,.0f}")

st.divider()

# ============ 客户分群分布 ============
st.subheader("👥 客户分群分布")
col_dist1, col_dist2 = st.columns(2)

with col_dist1:
    seg_count = filtered["客户分群"].value_counts().reset_index()
    seg_count.columns = ["客户分群", "人数"]
    fig_seg = px.bar(
        seg_count, x="客户分群", y="人数",
        color="客户分群",
        title="各分群客户数量",
        text="人数"
    )
    fig_seg.update_traces(textposition="outside")
    fig_seg.update_layout(showlegend=False, xaxis_tickangle=-30)
    st.plotly_chart(fig_seg, use_container_width=True)

with col_dist2:
    fig_pie = px.pie(
        seg_count, names="客户分群", values="人数",
        title="客户分群占比",
        hole=0.4
    )
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# ============ RFM 三维散点图 ============
st.subheader("🎯 RFM 三维分布")
fig_3d = px.scatter_3d(
    filtered,
    x="R_评分", y="F_评分", z="M_评分",
    color="客户分群",
    size="累计消费",
    hover_data=["会员ID", "R_天数", "购买次数", "累计消费"],
    opacity=0.7,
    title="客户 RFM 三维分布（点击图例筛选）"
)
fig_3d.update_layout(height=600)
st.plotly_chart(fig_3d, use_container_width=True)

st.divider()

# ============ R-F 热力图 ============
st.subheader("🔥 R-F 评分热力图")
col_hm1, col_hm2 = st.columns(2)

with col_hm1:
    rf_heatmap = filtered.groupby(["R_评分", "F_评分"]).size().reset_index(name="客户数")
    rf_pivot = rf_heatmap.pivot(index="F_评分", columns="R_评分", values="客户数").fillna(0)
    fig_rf = px.imshow(
        rf_pivot,
        labels=dict(x="R 评分", y="F 评分", color="客户数"),
        title="R-F 客户密度热力图",
        text_auto=True,
        color_continuous_scale="YlOrRd"
    )
    st.plotly_chart(fig_rf, use_container_width=True)

with col_hm2:
    fm_heatmap = filtered.groupby(["F_评分", "M_评分"]).size().reset_index(name="客户数")
    fm_pivot = fm_heatmap.pivot(index="M_评分", columns="F_评分", values="客户数").fillna(0)
    fig_fm = px.imshow(
        fm_pivot,
        labels=dict(x="F 评分", y="M 评分", color="客户数"),
        title="F-M 客户密度热力图",
        text_auto=True,
        color_continuous_scale="YlGnBu"
    )
    st.plotly_chart(fig_fm, use_container_width=True)

st.divider()

# ============ 各分群消费特征 ============
st.subheader("💰 各分群消费特征")
col_box1, col_box2 = st.columns(2)

with col_box1:
    fig_box1 = px.box(
        filtered, x="客户分群", y="累计消费",
        color="客户分群",
        title="各分群累计消费分布"
    )
    fig_box1.update_layout(showlegend=False, xaxis_tickangle=-30, yaxis_range=[0, filtered["累计消费"].quantile(0.95)])
    st.plotly_chart(fig_box1, use_container_width=True)

with col_box2:
    fig_box2 = px.box(
        filtered, x="客户分群", y="购买次数",
        color="客户分群",
        title="各分群购买次数分布"
    )
    fig_box2.update_layout(showlegend=False, xaxis_tickangle=-30, yaxis_range=[0, filtered["购买次数"].quantile(0.95)])
    st.plotly_chart(fig_box2, use_container_width=True)

st.divider()

# ============ 月度趋势 ============
st.subheader("📅 月度消费趋势")
df_merged = df.merge(rfm_scored[["会员ID", "客户分群"]], on="会员ID")
df_merged["月份"] = df_merged["提交日期"].dt.to_period("M").astype(str)

monthly_trend = df_merged.groupby(["月份", "客户分群"]).agg(
    订单数=("订单号", "nunique"),
    销售额=("订单金额", "sum")
).reset_index()

tab1, tab2 = st.tabs(["销售额趋势", "订单数趋势"])
with tab1:
    fig_mt1 = px.line(monthly_trend, x="月份", y="销售额", color="客户分群", title="各分群月度销售额")
    fig_mt1.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_mt1, use_container_width=True)
with tab2:
    fig_mt2 = px.line(monthly_trend, x="月份", y="订单数", color="客户分群", title="各分群月度订单数")
    fig_mt2.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_mt2, use_container_width=True)

st.divider()

# ============ 各分群详细数据 ============
st.subheader("📋 各分群详细统计")

seg_stats = rfm_scored.groupby("客户分群").agg(
    客户数=("会员ID", "count"),
    平均R_天=("R_天数", "mean"),
    平均F_次=("购买次数", "mean"),
    平均M_元=("累计消费", "mean"),
    平均客单价=("平均客单价", "mean"),
    平均生命周期_天=("客户生命周期", "mean"),
).round(1).reset_index()

st.dataframe(seg_stats, use_container_width=True)

st.divider()

# ============ 客户明细查询 ============
st.subheader("🔍 客户明细查询")
search_id = st.text_input("输入会员ID 查询")

if search_id:
    try:
        search_id_int = int(search_id)
        customer = rfm_scored[rfm_scored["会员ID"] == search_id_int]
        if not customer.empty:
            c = customer.iloc[0]
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("客户分群", c["客户分群"])
            mc2.metric("R（最近购买距今）", f"{c['R_天数']} 天")
            mc3.metric("F（购买次数）", f"{c['购买次数']} 次")
            mc4.metric("M（累计消费）", f"¥{c['累计消费']:,.0f}")

            # 该客户的订单记录
            customer_orders = df[df["会员ID"] == search_id_int].sort_values("提交日期", ascending=False)
            st.dataframe(customer_orders, use_container_width=True)
        else:
            st.warning("未找到该会员")
    except ValueError:
        st.warning("请输入有效的数字会员ID")
else:
    # 默认展示 top 客户
    st.caption("💡 输入会员ID查看详细信息，或浏览下方高价值客户")
    top_customers = rfm_scored.nlargest(20, "RFM_总分")[["会员ID", "客户分群", "R_天数", "购买次数", "累计消费", "R_评分", "F_评分", "M_评分", "RFM_总分"]]
    st.dataframe(top_customers, use_container_width=True)

# ============ 侧边栏底部统计 ============
st.sidebar.divider()
st.sidebar.markdown("### 📊 数据摘要")
st.sidebar.write(f"数据时间范围：{df['提交日期'].min().strftime('%Y-%m-%d')} ~ {df['提交日期'].max().strftime('%Y-%m-%d')}")
st.sidebar.write(f"总订单数：{len(df):,}")
st.sidebar.write(f"总客户数：{df['会员ID'].nunique():,}")
st.sidebar.write(f"总销售额：¥{df['订单金额'].sum():,.0f}")
