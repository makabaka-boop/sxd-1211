#!/bin/bash
BASE_URL="http://localhost:8144"
PASS=0
FAIL=0

assert_contains() {
    local desc="$1"
    local body="$2"
    local keyword="$3"
    if echo "$body" | grep -Fq "$keyword"; then
        echo "[PASS] $desc"
        PASS=$((PASS+1))
    else
        echo "[FAIL] $desc"
        echo "  期望包含: $keyword"
        echo "  实际返回: $(echo "$body" | head -c 400)"
        FAIL=$((FAIL+1))
    fi
}

assert_not_contains() {
    local desc="$1"
    local body="$2"
    local keyword="$3"
    if echo "$body" | grep -Fq "$keyword"; then
        echo "[FAIL] $desc"
        echo "  期望不包含: $keyword"
        echo "  实际返回: $(echo "$body" | head -c 400)"
        FAIL=$((FAIL+1))
    else
        echo "[PASS] $desc"
        PASS=$((PASS+1))
    fi
}

json_value() {
    local body="$1"
    local key="$2"
    echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$key',''))"
}

echo "=========================================="
echo "  出厂交接确认功能 - 验证测试"
echo "=========================================="
echo ""

ADMIN_TOKEN=$(curl -s -X POST $BASE_URL/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
SORTER_TOKEN=$(curl -s -X POST $BASE_URL/auth/login -H "Content-Type: application/json" -d '{"username":"sorter","password":"sorter123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
INSPECTOR_TOKEN=$(curl -s -X POST $BASE_URL/auth/login -H "Content-Type: application/json" -d '{"username":"inspector","password":"inspector123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

RUN_ID=$(date +%s)
B1="DH-READY-${RUN_ID}-1"
B2="DH-READY-${RUN_ID}-2"
B3="DH-READY-${RUN_ID}-3"
B4="DH-PENDING-${RUN_ID}-4"

# 准备一条「可出厂」布草（待交接）
RESULT=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d "{\"customer_id\":1,\"category_id\":1,\"batch_no\":\"$B1\",\"quantity\":120,\"stain_level\":\"中\",\"damage_description\":\"普通污渍\"}")
RECORD_ID=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d "{\"washing_line_id\":1,\"work_team_id\":1,\"sorting_line\":\"A分拣线\",\"washing_batch_no\":\"WD-${RUN_ID}-1\"}" > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null
curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"cleanliness":"良","damage_recheck":"无","delivery_suggestion":"同意出厂","qc_remark":"合格"}' > /dev/null
echo "待交接布草ID: $RECORD_ID"

# 准备第二条「可出厂」布草，保持待交接状态用于对比
RESULT2=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d "{\"customer_id\":1,\"category_id\":1,\"batch_no\":\"$B2\",\"quantity\":60,\"stain_level\":\"轻\",\"damage_description\":\"无\"}")
RECORD_ID2=$(echo $RESULT2 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID2/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d "{\"washing_line_id\":1,\"work_team_id\":1,\"sorting_line\":\"A分拣线\",\"washing_batch_no\":\"WD-${RUN_ID}-2\"}" > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID2/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null
curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID2/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"cleanliness":"优","damage_recheck":"无","delivery_suggestion":"同意出厂","qc_remark":"合格"}' > /dev/null
echo "第二条待交接布草ID: $RECORD_ID2"
echo ""

echo "=========================================="
echo "  1. 出厂交接确认：登记交接信息"
echo "=========================================="
DELIVERY_RESULT=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID/delivery -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "handover_person":"王交接",
  "customer_signee":"第一医院-张主任",
  "delivery_quantity":120,
  "handover_remark":"客户当场清点无误",
  "delivery_time":"2026-06-20T15:30:00"
}')
echo "交接结果: $DELIVERY_RESULT"

assert_contains "交接后状态为已出厂" "$DELIVERY_RESULT" '"status":"已出厂"'
assert_contains "交接记录包含交接人" "$DELIVERY_RESULT" '"handover_person":"王交接"'
assert_contains "交接记录包含客户签收人" "$DELIVERY_RESULT" '"customer_signee":"第一医院-张主任"'
assert_contains "交接记录包含出厂数量" "$DELIVERY_RESULT" '"delivery_quantity":120'
assert_contains "交接记录包含交接备注" "$DELIVERY_RESULT" '"客户当场清点无误"'
assert_contains "交接记录包含出厂时间" "$DELIVERY_RESULT" '"delivery_time":"2026-06-20T15:30:00"'
assert_contains "布草记录delivered_at已设置" "$DELIVERY_RESULT" '"delivered_at":"2026-06-20T15:30:00"'
assert_contains "返回delivery_stage为已完成交接" "$DELIVERY_RESULT" '"delivery_stage":"已完成交接"'
echo ""

echo "=========================================="
echo "  2. 布草详情展示完整出厂信息"
echo "=========================================="
DETAIL=$(curl -s $BASE_URL/inspector/cloth-records/$RECORD_ID/detail -H "Authorization: Bearer $INSPECTOR_TOKEN")
echo $DETAIL | python3 -c "
import sys,json
data = json.load(sys.stdin)
print(f'  delivery_stage: {data.get(\"delivery_stage\")}')
print(f'  delivered_at: {data.get(\"delivered_at\")}')
print(f'  delivery_records 数量: {len(data.get(\"delivery_records\", []))}')
"
assert_contains "详情delivery_stage为已完成交接" "$DETAIL" '"delivery_stage":"已完成交接"'
assert_contains "详情包含delivery_records" "$DETAIL" '"delivery_records":['
assert_contains "详情交接记录含交接人" "$DETAIL" '"handover_person":"王交接"'
assert_contains "详情交接记录含客户签收人" "$DETAIL" '"customer_signee":"第一医院-张主任"'
assert_contains "详情交接记录含操作人姓名" "$DETAIL" '"operator_name"'
assert_contains "详情包含出厂时间" "$DETAIL" '"delivery_time":"2026-06-20T15:30:00"'
echo ""

echo "=========================================="
echo "  3. 列表筛选区分待交接与已完成交接"
echo "=========================================="
PENDING_LIST=$(curl -s -G $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" --data-urlencode "delivery_stage=可出厂待交接")
COMPLETED_LIST=$(curl -s -G $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" --data-urlencode "delivery_stage=已完成交接")

PENDING_COUNT=$(echo "$PENDING_LIST" | python3 -c "import sys,json; data=json.load(sys.stdin); print(sum(1 for r in data if r['id']==$RECORD_ID))")
COMPLETED_COUNT=$(echo "$COMPLETED_LIST" | python3 -c "import sys,json; data=json.load(sys.stdin); print(sum(1 for r in data if r['id']==$RECORD_ID))")
echo "  已交接布草在「待交接」列表中出现次数: $PENDING_COUNT"
echo "  已交接布草在「已完成交接」列表中出现次数: $COMPLETED_COUNT"

if [ "$PENDING_COUNT" = "0" ]; then echo "[PASS] 已交接布草不在待交接列表"; PASS=$((PASS+1)); else echo "[FAIL] 已交接布草不应出现在待交接列表"; FAIL=$((FAIL+1)); fi
if [ "$COMPLETED_COUNT" = "1" ]; then echo "[PASS] 已交接布草在已完成交接列表"; PASS=$((PASS+1)); else echo "[FAIL] 已交接布草应在已完成交接列表"; FAIL=$((FAIL+1)); fi

assert_contains "待交接列表包含delivery_stage字段" "$PENDING_LIST" '"delivery_stage":"可出厂待交接"'
assert_contains "已完成列表包含delivery_stage字段" "$COMPLETED_LIST" '"delivery_stage":"已完成交接"'

READY_DELIVERED=$(curl -s $BASE_URL/inspector/cloth-records/delivered -H "Authorization: Bearer $INSPECTOR_TOKEN")
assert_contains "已完成交接快捷列表包含已交接记录" "$READY_DELIVERED" "\"batch_no\":\"$B1\""
READY_PENDING=$(curl -s $BASE_URL/inspector/cloth-records/ready-for-delivery -H "Authorization: Bearer $INSPECTOR_TOKEN")
assert_contains "待交接快捷列表包含待交接记录" "$READY_PENDING" "\"batch_no\":\"$B2\""
assert_not_contains "待交接快捷列表不含已交接记录" "$READY_PENDING" "\"batch_no\":\"$B1\""
echo ""

echo "=========================================="
echo "  4. 统计摘要区分两种状态"
echo "=========================================="
SUMMARY=$(curl -s $BASE_URL/stats/summary -H "Authorization: Bearer $INSPECTOR_TOKEN")
echo $SUMMARY | python3 -c "
import sys,json
data = json.load(sys.stdin)
d = data.get('delivery', {})
print(f'  待交接批次: {d.get(\"pending_handover_count\")}')
print(f'  已完成交接批次: {d.get(\"completed_handover_count\")}')
print(f'  交接完成率: {d.get(\"handover_completion_rate\")}%')
"
assert_contains "统计摘要含delivery对象" "$SUMMARY" '"delivery":{'
assert_contains "统计摘要含pending_handover_count" "$SUMMARY" '"pending_handover_count":'
assert_contains "统计摘要含completed_handover_count" "$SUMMARY" '"completed_handover_count":'
assert_contains "统计摘要含handover_completion_rate" "$SUMMARY" '"handover_completion_rate":'
assert_contains "统计摘要status_counts含已出厂" "$SUMMARY" '"已出厂":'
echo ""

echo "=========================================="
echo "  5. 客户维度统计区分两种状态"
echo "=========================================="
BY_CUSTOMER=$(curl -s $BASE_URL/stats/delivery/by-customer -H "Authorization: Bearer $INSPECTOR_TOKEN")
echo $BY_CUSTOMER | python3 -c "
import sys,json
data = json.load(sys.stdin)
for c in data:
    if c.get('customer_id') == 1:
        print(f'  客户: {c.get(\"customer_name\")}')
        print(f'  待交接批次: {c.get(\"pending_handover_count\")}')
        print(f'  已完成交接批次: {c.get(\"completed_handover_count\")}')
        print(f'  已交接数量: {c.get(\"delivered_quantity\")}')
        print(f'  交接完成率: {c.get(\"handover_completion_rate\")}%')
"
assert_contains "客户维度含pending_handover_count" "$BY_CUSTOMER" '"pending_handover_count":'
assert_contains "客户维度含completed_handover_count" "$BY_CUSTOMER" '"completed_handover_count":'
assert_contains "客户维度含delivered_quantity" "$BY_CUSTOMER" '"delivered_quantity":'
assert_contains "客户维度含handover_completion_rate" "$BY_CUSTOMER" '"handover_completion_rate":'

OVERVIEW=$(curl -s $BASE_URL/stats/delivery/overview -H "Authorization: Bearer $INSPECTOR_TOKEN")
assert_contains "交接概览含completed_handover_count" "$OVERVIEW" '"completed_handover_count":'
assert_contains "交接概览含total_delivery_records" "$OVERVIEW" '"total_delivery_records":'
echo ""

echo "=========================================="
echo "  6. 边界校验"
echo "=========================================="
# 已出厂不可重复交接
RE_DELIVER=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID/delivery -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"handover_person":"王交接","customer_signee":"第一医院-张主任"}')
assert_contains "已出厂不可重复交接" "$RE_DELIVER" "不可出厂交接"

# 缺少交接人
RESULT3=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d "{\"customer_id\":1,\"category_id\":1,\"batch_no\":\"$B3\",\"quantity\":40,\"stain_level\":\"轻\",\"damage_description\":\"无\"}")
RECORD_ID3=$(echo $RESULT3 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID3/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d "{\"washing_line_id\":1,\"work_team_id\":1,\"sorting_line\":\"A分拣线\",\"washing_batch_no\":\"WD-${RUN_ID}-3\"}" > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID3/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null
curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID3/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"cleanliness":"优","damage_recheck":"无","delivery_suggestion":"同意出厂"}' > /dev/null

NO_PERSON=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID3/delivery -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"handover_person":"","customer_signee":"签收人"}')
assert_contains "缺少交接人被拒绝" "$NO_PERSON" "交接人不能为空"

NO_SIGNEE=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID3/delivery -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"handover_person":"交接人","customer_signee":""}')
assert_contains "缺少客户签收人被拒绝" "$NO_SIGNEE" "客户签收人不能为空"

OVER_QTY=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID3/delivery -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"handover_person":"交接人","customer_signee":"签收人","delivery_quantity":999}')
assert_contains "出厂数量超限被拒绝" "$OVER_QTY" "不可超过布草记录数量"

# 默认出厂数量=记录数量且出厂时间为当前时间
DEFAULT_QTY=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID3/delivery -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"handover_person":"李交接","customer_signee":"签收人"}')
assert_contains "默认出厂数量为记录数量" "$DEFAULT_QTY" '"delivery_quantity":40'
assert_contains "默认出厂时间已生成" "$DEFAULT_QTY" '"delivery_time":"'
assert_contains "默认交接后状态为已出厂" "$DEFAULT_QTY" '"status":"已出厂"'

# 非可出厂状态不可交接（待质检）
RESULT4=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d "{\"customer_id\":1,\"category_id\":1,\"batch_no\":\"$B4\",\"quantity\":20,\"stain_level\":\"轻\",\"damage_description\":\"无\"}")
RECORD_ID4=$(echo $RESULT4 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID4/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d "{\"washing_line_id\":1,\"work_team_id\":1,\"sorting_line\":\"A分拣线\",\"washing_batch_no\":\"WD-${RUN_ID}-4\"}" > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID4/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null
WRONG_STATUS=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID4/delivery -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"handover_person":"交接人","customer_signee":"签收人"}')
assert_contains "非可出厂状态不可交接" "$WRONG_STATUS" "不可出厂交接"
echo ""

echo "=========================================="
echo "  测试结果汇总"
echo "=========================================="
echo "通过: $PASS"
echo "失败: $FAIL"
if [ $FAIL -eq 0 ]; then
    echo "全部出厂交接确认功能验证通过！"
else
    echo "有 $FAIL 个测试失败"
fi
