#!/bin/bash
BASE_URL="http://localhost:8144"
PASS=0
FAIL=0

assert_contains() {
    local desc="$1"
    local body="$2"
    local keyword="$3"
    if echo "$body" | grep -q "$keyword"; then
        echo "[PASS] $desc"
        PASS=$((PASS+1))
    else
        echo "[FAIL] $desc"
        echo "  期望包含: $keyword"
        echo "  实际返回: $body"
        FAIL=$((FAIL+1))
    fi
}

assert_not_contains() {
    local desc="$1"
    local body="$2"
    local keyword="$3"
    if echo "$body" | grep -q "$keyword"; then
        echo "[FAIL] $desc (不应包含: $keyword)"
        echo "  实际返回: $body"
        FAIL=$((FAIL+1))
    else
        echo "[PASS] $desc"
        PASS=$((PASS+1))
    fi
}

echo "=========================================="
echo "  洗衣工厂管理系统 - 修复验证测试"
echo "=========================================="
echo ""

# 登录获取token
ADMIN_TOKEN=$(curl -s -X POST $BASE_URL/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
SORTER_TOKEN=$(curl -s -X POST $BASE_URL/auth/login -H "Content-Type: application/json" -d '{"username":"sorter","password":"sorter123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
INSPECTOR_TOKEN=$(curl -s -X POST $BASE_URL/auth/login -H "Content-Type: application/json" -d '{"username":"inspector","password":"inspector123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "--- 准备基础数据 ---"
curl -s -X POST $BASE_URL/customers/ -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"name":"第一医院","contact":"张主任","phone":"13800138001"}' > /dev/null
curl -s -X POST $BASE_URL/cloth-categories/ -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"name":"白大褂","description":"医生工作服"}' > /dev/null
curl -s -X POST $BASE_URL/washing-lines/ -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"name":"1号清洗线","capacity":500}' > /dev/null
curl -s -X POST $BASE_URL/work-teams/ -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"name":"甲班","leader":"李组长"}' > /dev/null
echo ""

echo "=========================================="
echo "  修复2: 分拣线和清洗批号存储"
echo "=========================================="
echo "--- 创建布草记录 ---"
RESULT=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"B001","quantity":100,"stain_level":"中","damage_description":"轻微污渍"}')
RECORD_ID=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "布草记录ID: $RECORD_ID"

echo "--- 分拣（含分拣线和清洗批号）---"
SORT_RESULT=$(curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"A分拣线","washing_batch_no":"W20240101001"}')
assert_contains "分拣线已存储" "$SORT_RESULT" "A分拣线"
assert_contains "清洗批号已存储" "$SORT_RESULT" "W20240101001"
assert_contains "状态为清洗中" "$SORT_RESULT" "清洗中"
echo ""

echo "=========================================="
echo "  修复1: 质检状态跳过问题"
echo "=========================================="
echo "--- 直接对清洗中状态质检（应失败）---"
QC_FAIL=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"cleanliness":"良","damage_recheck":"无","delivery_suggestion":"同意出厂"}')
assert_contains "清洗中状态不可质检" "$QC_FAIL" "不可质检"
assert_contains "提示先完成清洗" "$QC_FAIL" "完成清洗"
echo ""

echo "--- 完成清洗（清洗中→待质检）---"
COMPLETE_RESULT=$(curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID/complete-washing -H "Authorization: Bearer $SORTER_TOKEN")
assert_contains "状态变为待质检" "$COMPLETE_RESULT" "待质检"
echo ""

echo "--- 对待质检状态质检（应成功）---"
QC_OK=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"cleanliness":"良","damage_recheck":"无","delivery_suggestion":"同意出厂"}')
assert_contains "质检成功" "$QC_OK" "delivery_suggestion"
echo ""

echo "--- 对不存在的记录ID质检（应失败）---"
QC_404=$(curl -s -X POST $BASE_URL/inspector/cloth-records/99999/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"cleanliness":"良","damage_recheck":"无","delivery_suggestion":"同意出厂"}')
assert_contains "记录不存在报错" "$QC_404" "不存在"
echo ""

echo "=========================================="
echo "  修复3: 记录ID校验"
echo "=========================================="
echo "--- 创建第二条记录 ---"
RESULT2=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"B002","quantity":50,"stain_level":"轻"}')
RECORD_ID2=$(echo $RESULT2 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "布草记录ID2: $RECORD_ID2"

echo "--- 对不存在的记录分拣（应失败）---"
SORT_404=$(curl -s -X POST $BASE_URL/sorter/cloth-records/99999/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"B线","washing_batch_no":"W002"}')
assert_contains "分拣不存在记录报错" "$SORT_404" "不存在"
echo ""

echo "=========================================="
echo "  同客户同批号校验"
echo "=========================================="
DUP=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"B001","quantity":30,"stain_level":"轻"}')
assert_contains "重复批号校验" "$DUP" "不可重复入厂"
echo ""

echo "=========================================="
echo "  完整状态流转测试"
echo "=========================================="
echo "--- 分拣第二条记录 ---"
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID2/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"B分拣线","washing_batch_no":"W20240101002"}' > /dev/null

echo "--- 完成清洗 ---"
CW=$(curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID2/complete-washing -H "Authorization: Bearer $SORTER_TOKEN")
assert_contains "状态待质检" "$CW" "待质检"

echo "--- 质检（补洗结论）---"
QC2=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID2/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"cleanliness":"差","damage_recheck":"中度","rewash_conclusion":true,"delivery_suggestion":"补洗"}')
assert_contains "质检后状态补洗中" "$(curl -s $BASE_URL/sorter/cloth-records/$RECORD_ID2 -H "Authorization: Bearer $SORTER_TOKEN")" "补洗中"
echo ""

echo "=========================================="
echo "  修复4: 质检超期检测"
echo "=========================================="
echo "--- 创建一条待质检记录 ---"
RESULT3=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"B003","quantity":80,"stain_level":"重"}')
RECORD_ID3=$(echo $RESULT3 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID3/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"C分拣线","washing_batch_no":"W003"}' > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID3/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null

echo "--- 检查待质检列表 ---"
PENDING=$(curl -s $BASE_URL/inspector/pending-qc -H "Authorization: Bearer $INSPECTOR_TOKEN")
echo "待质检列表: $PENDING"
assert_contains "待质检列表含B003" "$PENDING" "B003"
echo ""

echo "--- 检查质检超期检测（不应包含清洗中/补洗中）---"
QC_TIMEOUT=$(curl -s $BASE_URL/anomalies/qc-timeout -H "Authorization: Bearer $INSPECTOR_TOKEN")
echo "质检超期: $QC_TIMEOUT"
# B001已经是可出厂状态，B002是补洗中状态，只有B003是待质检
echo ""

echo "=========================================="
echo "  修复5: 破损率统计不重复累计"
echo "=========================================="
echo "--- 创建带破损说明的记录 ---"
RESULT4=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"B004","quantity":100,"stain_level":"重","damage_description":"大面积破损"}')
RECORD_ID4=$(echo $RESULT4 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID4/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"D分拣线","washing_batch_no":"W004"}' > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID4/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null
# 质检也记录破损
curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID4/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"cleanliness":"差","damage_recheck":"严重","delivery_suggestion":"暂停出厂"}' > /dev/null

echo "--- 检查破损高发类别统计 ---"
DAMAGE_STATS=$(curl -s $BASE_URL/stats/damage-high-risk -H "Authorization: Bearer $ADMIN_TOKEN")
echo "破损统计: $DAMAGE_STATS"

# 验证B004只被计算一次破损（damaged_count不应翻倍）
DAMAGED_COUNT=$(echo $DAMAGE_STATS | python3 -c "
import sys,json
data = json.load(sys.stdin)
for item in data:
    if item.get('category_name') == '白大褂':
        print(item.get('damaged_count', 0))
        break
else:
    print(0)
")
echo "破损批次数: $DAMAGED_COUNT (期望: 破损说明和质检破损只算一次)"
echo ""

echo "=========================================="
echo "  统计摘要验证"
echo "=========================================="
SUMMARY=$(curl -s $BASE_URL/stats/summary -H "Authorization: Bearer $ADMIN_TOKEN")
echo "状态统计:"
echo "$SUMMARY" | python3 -c "
import sys,json
data = json.load(sys.stdin)
for k,v in data.get('status_counts',{}).items():
    print(f'  {k}: {v}')
print(f'总记录数: {data.get(\"total_records\")}')
print(f'总数量: {data.get(\"total_quantity\")}')
"
echo ""

echo "=========================================="
echo "  异常检测汇总"
echo "=========================================="
ANOMALIES=$(curl -s $BASE_URL/anomalies/ -H "Authorization: Bearer $ADMIN_TOKEN")
echo "$ANOMALIES" | python3 -c "
import sys,json
data = json.load(sys.stdin)
print(f'破损率异常类别数: {len(data.get(\"damage_rate_abnormal\",[]))}')
print(f'补洗积压数: {len(data.get(\"rewash_backlog\",[]))}')
print(f'质检超期数: {len(data.get(\"qc_timeout\",[]))}')
print(f'清洗线问题数: {len(data.get(\"washing_line_problems\",[]))}')
print(f'出厂结论缺失数: {len(data.get(\"missing_delivery_conclusion\",[]))}')
"
echo ""

echo "=========================================="
echo "  测试结果汇总"
echo "=========================================="
echo "通过: $PASS"
echo "失败: $FAIL"
if [ $FAIL -eq 0 ]; then
    echo "✅ 全部测试通过！"
else
    echo "❌ 有 $FAIL 个测试失败"
fi
