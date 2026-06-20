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
        echo "  实际返回: $(echo "$body" | head -c 300)"
        FAIL=$((FAIL+1))
    fi
}

assert_not_contains() {
    local desc="$1"
    local body="$2"
    local keyword="$3"
    if echo "$body" | grep -q "$keyword"; then
        echo "[FAIL] $desc"
        echo "  期望不包含: $keyword"
        echo "  实际返回: $(echo "$body" | head -c 300)"
        FAIL=$((FAIL+1))
    else
        echo "[PASS] $desc"
        PASS=$((PASS+1))
    fi
}

echo "=========================================="
echo "  补洗闭环 - 5个问题修复验证测试"
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
echo "基础数据准备完成"
echo ""

echo "=========================================="
echo "  问题1：复检结论为暂停出厂时任务状态被记为复检通过"
echo "=========================================="
RESULT=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"TEST-HOLD-001","quantity":100,"stain_level":"中","damage_description":"轻微污渍"}')
RECORD_ID=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"A分拣线","washing_batch_no":"W001"}' > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null

# 质检打回补洗（附带补洗任务信息，自动创建补洗任务）
QC_RESULT=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "cleanliness": "差",
  "damage_recheck": "轻微",
  "delivery_suggestion": "补洗",
  "qc_remark": "领口污渍严重",
  "rewash_reason": "领口污渍未清洗干净",
  "rewash_severity": "中",
  "rewash_expected_completion_time": "2026-06-21T18:00:00",
  "rewash_responsible_washing_line_id": 1,
  "rewash_responsible_work_team_id": 1
}')
TASK_ID=$(echo $QC_RESULT | python3 -c "import sys,json; print(json.load(sys.stdin).get('rewash_task',{}).get('id',0))")
echo "补洗任务ID: $TASK_ID"

# 启动补洗、完成补洗
curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID/start -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null
curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID/complete -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"completion_remark":"已清洗完成"}' > /dev/null

# 复检 - 暂停出厂
RECHECK_RESULT=$(curl -s -X POST $BASE_URL/inspector/rewash-tasks/$TASK_ID/recheck -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "cleanliness": "良",
  "damage_recheck": "轻微",
  "final_conclusion": "暂停出厂",
  "recheck_remark": "需进一步确认"
}')
echo "复检结果: $RECHECK_RESULT"

# 验证补洗任务状态不是"复检通过"
TASK_DETAIL=$(curl -s $BASE_URL/inspector/rewash-tasks/$TASK_ID -H "Authorization: Bearer $INSPECTOR_TOKEN")
echo "补洗任务详情: $TASK_DETAIL"

assert_not_contains "暂停出厂的补洗任务状态不是复检通过" "$TASK_DETAIL" '"status":"复检通过"'
assert_contains "暂停出厂的补洗任务状态是暂停出厂" "$TASK_DETAIL" '"status":"暂停出厂"'

# 验证布草状态
RECORD_STATUS=$(curl -s $BASE_URL/sorter/cloth-records/$RECORD_ID -H "Authorization: Bearer $SORTER_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', ''))")
echo "布草状态: $RECORD_STATUS"
assert_contains "布草状态为暂停出厂" "$RECORD_STATUS" "暂停出厂"
echo ""

echo "=========================================="
echo "  问题2：补洗可以没开始就完成，时间记录不准确"
echo "=========================================="
RESULT2=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"TEST-START-001","quantity":50,"stain_level":"中","damage_description":"普通污渍"}')
RECORD_ID2=$(echo $RESULT2 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID2/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"A分拣线","washing_batch_no":"W002"}' > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID2/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null

# 质检打回补洗（自动创建补洗任务）
QC_RESULT2=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID2/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "cleanliness": "差",
  "damage_recheck": "无",
  "delivery_suggestion": "补洗",
  "qc_remark": "污渍未清",
  "rewash_reason": "整体污渍未清洗干净",
  "rewash_severity": "低",
  "rewash_expected_completion_time": "2026-06-22T12:00:00",
  "rewash_responsible_washing_line_id": 1,
  "rewash_responsible_work_team_id": 1
}')
TASK_ID2=$(echo $QC_RESULT2 | python3 -c "import sys,json; print(json.load(sys.stdin).get('rewash_task',{}).get('id',0))")
echo "补洗任务ID: $TASK_ID2"

# 尝试未启动就完成（应该报错）
COMPLETE_FAIL=$(curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID2/complete -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"completion_remark":"直接完成"}')
echo "未启动就完成的结果: $COMPLETE_FAIL"
assert_contains "未启动的补洗任务不可直接完成" "$COMPLETE_FAIL" "尚未启动"

# 验证任务状态仍然是待补洗
TASK_DETAIL2=$(curl -s $BASE_URL/sorter/rewash-tasks/$TASK_ID2 -H "Authorization: Bearer $SORTER_TOKEN")
assert_contains "任务状态仍为待补洗" "$TASK_DETAIL2" '"status":"待补洗"'
assert_not_contains "任务started_at为空" "$TASK_DETAIL2" '"started_at":"'

# 启动后再完成（应该成功）
START_RESULT=$(curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID2/start -H "Authorization: Bearer $SORTER_TOKEN")
assert_contains "启动补洗任务成功" "$START_RESULT" '"status":"补洗中"'

COMPLETE_RESULT=$(curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID2/complete -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"completion_remark":"已完成补洗"}')
assert_contains "启动后完成补洗任务成功" "$COMPLETE_RESULT" '"status":"补洗完成待复检"'

# 验证时间记录
TASK_DETAIL3=$(curl -s $BASE_URL/sorter/rewash-tasks/$TASK_ID2 -H "Authorization: Bearer $SORTER_TOKEN")
assert_contains "有started_at时间记录" "$TASK_DETAIL3" '"started_at":"'
assert_contains "有completed_at时间记录" "$TASK_DETAIL3" '"completed_at":"'
echo ""

echo "=========================================="
echo "  问题3：质检打回补洗后没有生成完整补洗任务"
echo "=========================================="
RESULT3=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"TEST-AUTO-001","quantity":80,"stain_level":"重","damage_description":"大面积污渍"}')
RECORD_ID3=$(echo $RESULT3 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID3/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"A分拣线","washing_batch_no":"W003"}' > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID3/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null

# 质检打回补洗（附带补洗任务信息）
QC_RESULT3=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID3/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "cleanliness": "差",
  "damage_recheck": "中度",
  "delivery_suggestion": "补洗",
  "qc_remark": "大面积污渍未清",
  "rewash_reason": "大面积顽固污渍未清洗干净",
  "rewash_severity": "严重",
  "rewash_expected_completion_time": "2026-06-23T12:00:00",
  "rewash_responsible_washing_line_id": 1,
  "rewash_responsible_work_team_id": 1,
  "rewash_remark": "请使用加强型洗涤剂"
}')
echo "质检返回: $QC_RESULT3"

# 验证自动创建了补洗任务（直接从原始JSON响应断言）
assert_contains "质检打回补洗后自动生成补洗任务" "$QC_RESULT3" '"rewash_task":{'
assert_contains "补洗任务包含原因" "$QC_RESULT3" "大面积顽固污渍未清洗干净"
assert_contains "补洗任务包含严重程度" "$QC_RESULT3" '"severity":"严重"'
assert_contains "补洗任务包含期望完成时间" "$QC_RESULT3" "2026-06-23T12:00:00"
assert_contains "补洗任务包含责任清洗线" "$QC_RESULT3" '"responsible_washing_line_id":1'
assert_contains "补洗任务包含责任班组" "$QC_RESULT3" '"responsible_work_team_id":1'
assert_contains "补洗任务状态为待补洗" "$QC_RESULT3" '"status":"待补洗"'
assert_contains "补洗次数为1" "$QC_RESULT3" '"rewash_count":1'

# 验证布草状态为补洗中
RECORD_STATUS3=$(curl -s $BASE_URL/sorter/cloth-records/$RECORD_ID3 -H "Authorization: Bearer $SORTER_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', ''))")
assert_contains "布草状态为补洗中" "$RECORD_STATUS3" "补洗中"
echo ""

echo "=========================================="
echo "  问题4：复检不通过后没有下一步补洗任务"
echo "=========================================="
# 获取刚才创建的补洗任务ID
TASK_ID3=$(echo $QC_RESULT3 | python3 -c "import sys,json; print(json.load(sys.stdin).get('rewash_task',{}).get('id',0))")
echo "补洗任务ID: $TASK_ID3"

# 启动并完成补洗
curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID3/start -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null
curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID3/complete -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"completion_remark":"第一次补洗完成"}' > /dev/null

# 复检 - 继续补洗（附带下一次补洗任务信息）
RECHECK_RESULT2=$(curl -s -X POST $BASE_URL/inspector/rewash-tasks/$TASK_ID3/recheck -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "cleanliness": "差",
  "damage_recheck": "中度",
  "final_conclusion": "继续补洗",
  "recheck_remark": "污渍仍有残留，需再次补洗",
  "next_rewash_reason": "顽固污渍仍有残留，需深度清洗",
  "next_rewash_severity": "高",
  "next_rewash_expected_completion_time": "2026-06-24T12:00:00",
  "next_rewash_responsible_washing_line_id": 1,
  "next_rewash_responsible_work_team_id": 1,
  "next_rewash_remark": "请使用高温高压洗涤"
}')
echo "复检结果: $RECHECK_RESULT2"

# 验证自动创建了下一个补洗任务（直接从原始JSON响应断言）
assert_contains "复检不通过后自动创建新的补洗任务" "$RECHECK_RESULT2" '"next_rewash_task":{'
assert_contains "新补洗任务包含原因" "$RECHECK_RESULT2" "顽固污渍仍有残留"
assert_contains "新补洗任务严重程度为高" "$RECHECK_RESULT2" '"severity":"高"'
assert_contains "新补洗任务状态为待补洗" "$RECHECK_RESULT2" '"status":"待补洗"'

NEXT_TASK_ID=$(echo $RECHECK_RESULT2 | python3 -c "import sys,json; print(json.load(sys.stdin).get('next_rewash_task',{}).get('id',0))")
echo "新补洗任务ID: $NEXT_TASK_ID"

# 验证原任务状态为复检未通过
OLD_TASK=$(curl -s $BASE_URL/inspector/rewash-tasks/$TASK_ID3 -H "Authorization: Bearer $INSPECTOR_TOKEN")
assert_contains "原补洗任务状态为复检未通过" "$OLD_TASK" '"status":"复检未通过"'

# 验证新补洗任务的补洗次数是2
NEW_TASK=$(curl -s $BASE_URL/inspector/rewash-tasks/$NEXT_TASK_ID -H "Authorization: Bearer $INSPECTOR_TOKEN")
assert_contains "新补洗任务的补洗次数为2" "$NEW_TASK" '"rewash_count":2'

# 验证布草状态仍是补洗中
RECORD_STATUS4=$(curl -s $BASE_URL/sorter/cloth-records/$RECORD_ID3 -H "Authorization: Bearer $SORTER_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', ''))")
assert_contains "布草状态仍为补洗中" "$RECORD_STATUS4" "补洗中"

# 验证布草详情中有多个补洗任务
RECORD_DETAIL=$(curl -s $BASE_URL/inspector/cloth-records/$RECORD_ID3/detail -H "Authorization: Bearer $INSPECTOR_TOKEN")
echo $RECORD_DETAIL | python3 -c "
import sys,json
data = json.load(sys.stdin)
print(f'  总补洗次数: {data.get(\"total_rewash_count\", 0)}')
print(f'  补洗任务数量: {len(data.get(\"rewash_tasks\", []))}')
print(f'  复检历史数量: {len(data.get(\"recheck_history\", []))}')
"
assert_contains "布草详情中补洗任务数量>=2" "$RECORD_DETAIL" '"total_rewash_count":2'
echo ""

echo "=========================================="
echo "  问题5：补洗任务能被提前或随意创建"
echo "=========================================="

# 创建一条新布草，状态为待分拣
RESULT4=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"TEST-RANDOM-001","quantity":30,"stain_level":"轻","damage_description":"无"}')
RECORD_ID4=$(echo $RESULT4 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 尝试在待分拣状态创建补洗任务（应该失败）
CREATE_FAIL1=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID4/rewash-tasks -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "reason": "测试随意创建",
  "severity": "低",
  "expected_completion_time": "2026-06-25T12:00:00",
  "responsible_washing_line_id": 1,
  "responsible_work_team_id": 1
}')
echo "待分拣状态创建补洗任务结果: $CREATE_FAIL1"
assert_contains "待分拣状态不可创建补洗任务" "$CREATE_FAIL1" "不可创建补洗任务"

# 分拣后状态为清洗中，尝试创建补洗任务（应该失败）
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID4/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"A分拣线","washing_batch_no":"W004"}' > /dev/null

CREATE_FAIL2=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID4/rewash-tasks -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "reason": "测试随意创建",
  "severity": "低",
  "expected_completion_time": "2026-06-25T12:00:00",
  "responsible_washing_line_id": 1,
  "responsible_work_team_id": 1
}')
echo "清洗中状态创建补洗任务结果: $CREATE_FAIL2"
assert_contains "清洗中状态不可创建补洗任务" "$CREATE_FAIL2" "不可创建补洗任务"

# 完成清洗后状态为待质检，尝试创建补洗任务（应该失败）
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID4/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null

CREATE_FAIL3=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID4/rewash-tasks -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "reason": "测试随意创建",
  "severity": "低",
  "expected_completion_time": "2026-06-25T12:00:00",
  "responsible_washing_line_id": 1,
  "responsible_work_team_id": 1
}')
echo "待质检状态创建补洗任务结果: $CREATE_FAIL3"
assert_contains "待质检状态不可创建补洗任务" "$CREATE_FAIL3" "不可创建补洗任务"

# 质检打回补洗后状态为补洗中，尝试创建补洗任务（应该成功）
curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID4/qc -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "cleanliness": "差",
  "damage_recheck": "无",
  "delivery_suggestion": "补洗",
  "qc_remark": "测试"
}' > /dev/null

# 验证补洗中状态可以通过独立接口创建补洗任务
CREATE_SUCCESS=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID4/rewash-tasks -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "reason": "补洗中状态手动创建任务",
  "severity": "中",
  "expected_completion_time": "2026-06-25T12:00:00",
  "responsible_washing_line_id": 1,
  "responsible_work_team_id": 1
}')
echo "补洗中状态创建补洗任务结果: $CREATE_SUCCESS"
assert_contains "补洗中状态可以创建补洗任务" "$CREATE_SUCCESS" '"id"'
assert_contains "补洗任务原因为手动创建" "$CREATE_SUCCESS" "补洗中状态手动创建任务"

# 验证有进行中的任务时不能再创建
CREATE_FAIL4=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID4/rewash-tasks -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "reason": "重复创建测试",
  "severity": "低",
  "expected_completion_time": "2026-06-26T12:00:00",
  "responsible_washing_line_id": 1,
  "responsible_work_team_id": 1
}')
echo "有进行中任务时再次创建结果: $CREATE_FAIL4"
assert_contains "有进行中的补洗任务时不能再创建" "$CREATE_FAIL4" "已有进行中的补洗任务"
echo ""

echo "=========================================="
echo "  测试结果汇总"
echo "=========================================="
echo "通过: $PASS"
echo "失败: $FAIL"
if [ $FAIL -eq 0 ]; then
    echo "✅ 全部5个问题修复验证通过！"
else
    echo "❌ 有 $FAIL 个测试失败"
fi
