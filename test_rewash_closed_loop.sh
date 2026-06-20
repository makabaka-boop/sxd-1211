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

echo "=========================================="
echo "  补洗闭环跟踪与责任追溯 - 功能测试"
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
echo "  1. 创建布草记录并完成清洗和质检"
echo "=========================================="
RESULT=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"RW001","quantity":100,"stain_level":"中","damage_description":"轻微污渍"}')
RECORD_ID=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "布草记录ID: $RECORD_ID"

# 分拣
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"A分拣线","washing_batch_no":"W20240101001"}' > /dev/null
# 完成清洗
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null
echo "布草记录已完成清洗，状态待质检"
echo ""

echo "=========================================="
echo "  2. 质检员创建补洗任务"
echo "=========================================="
TASK_RESULT=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID/rewash-tasks -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "reason": "领口污渍未清洗干净",
  "severity": "中",
  "expected_completion_time": "2026-06-21T18:00:00",
  "responsible_washing_line_id": 1,
  "responsible_work_team_id": 1,
  "remark": "请重点清洗领口部位"
}')
echo "创建补洗任务结果: $TASK_RESULT"
TASK_ID=$(echo $TASK_RESULT | python3 -c "import sys,json; print(json.load(sys.stdin).get('id', 0))")
echo "补洗任务ID: $TASK_ID"

assert_contains "补洗任务创建成功（含原因）" "$TASK_RESULT" "领口污渍未清洗干净"
assert_contains "补洗任务创建成功（含严重程度）" "$TASK_RESULT" "中"
assert_contains "补洗任务状态为待补洗" "$TASK_RESULT" "待补洗"
assert_contains "补洗次数为1" "$TASK_RESULT" '"rewash_count":1'

# 验证布草状态变更为补洗中
RECORD_STATUS=$(curl -s $BASE_URL/sorter/cloth-records/$RECORD_ID -H "Authorization: Bearer $SORTER_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', ''))")
echo "布草记录当前状态: $RECORD_STATUS"
assert_contains "布草状态变更为补洗中" "$RECORD_STATUS" "补洗中"
echo ""

echo "=========================================="
echo "  3. 分拣员查看待补洗任务列表"
echo "=========================================="
PENDING_TASKS=$(curl -s $BASE_URL/sorter/rewash-tasks/pending -H "Authorization: Bearer $SORTER_TOKEN")
echo "待补洗任务列表: $PENDING_TASKS"
assert_contains "待补洗列表包含新任务" "$PENDING_TASKS" "RW001"
assert_contains "待补洗列表包含客户名称" "$PENDING_TASKS" "第一医院"
assert_contains "待补洗列表包含责任清洗线名称" "$PENDING_TASKS" "1号清洗线"
echo ""

echo "=========================================="
echo "  4. 分拣员启动补洗任务"
echo "=========================================="
START_RESULT=$(curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID/start -H "Authorization: Bearer $SORTER_TOKEN")
echo "启动补洗任务结果: $START_RESULT"
assert_contains "启动后状态变更为补洗中" "$START_RESULT" "补洗中"
assert_contains "启动时间已记录" "$START_RESULT" '"started_at"'
echo ""

echo "=========================================="
echo "  5. 分拣员提交补洗完成结果"
echo "=========================================="
COMPLETE_RESULT=$(curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID/complete -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{
  "completion_remark": "已使用高温加酶洗涤，领口污渍已清除"
}')
echo "完成补洗任务结果: $COMPLETE_RESULT"
assert_contains "完成后状态变更为补洗完成待复检" "$COMPLETE_RESULT" "补洗完成待复检"
assert_contains "完成备注已记录" "$COMPLETE_RESULT" "已使用高温加酶洗涤"
assert_contains "完成人ID已记录" "$COMPLETE_RESULT" '"completer_id"'

# 验证布草状态变更为待质检
RECORD_STATUS2=$(curl -s $BASE_URL/sorter/cloth-records/$RECORD_ID -H "Authorization: Bearer $SORTER_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', ''))")
echo "布草记录当前状态: $RECORD_STATUS2"
assert_contains "补洗完成后布草状态变为待质检" "$RECORD_STATUS2" "待质检"
echo ""

echo "=========================================="
echo "  6. 质检员对补洗后布草复检（通过-最终出厂）"
echo "=========================================="
RECHECK_RESULT=$(curl -s -X POST $BASE_URL/inspector/rewash-tasks/$TASK_ID/recheck -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "cleanliness": "优",
  "damage_recheck": "无",
  "final_conclusion": "最终出厂",
  "recheck_remark": "复检合格，污渍已完全清除"
}')
echo "复检结果: $RECHECK_RESULT"
assert_contains "复检结论为最终出厂" "$RECHECK_RESULT" "最终出厂"
assert_contains "复检洁净度已记录" "$RECHECK_RESULT" "优"

# 验证补洗任务状态
TASK_DETAIL=$(curl -s $BASE_URL/inspector/rewash-tasks/$TASK_ID -H "Authorization: Bearer $INSPECTOR_TOKEN")
assert_contains "补洗任务状态变更为复检通过" "$TASK_DETAIL" "复检通过"

# 验证布草状态变更为可出厂
RECORD_STATUS3=$(curl -s $BASE_URL/sorter/cloth-records/$RECORD_ID -H "Authorization: Bearer $SORTER_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', ''))")
echo "布草记录当前状态: $RECORD_STATUS3"
assert_contains "复检通过后布草状态变为可出厂" "$RECORD_STATUS3" "可出厂"
echo ""

echo "=========================================="
echo "  7. 创建第二个补洗任务测试继续补洗流程"
echo "=========================================="
# 创建另一条布草记录
RESULT2=$(curl -s -X POST $BASE_URL/sorter/cloth-records -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"customer_id":1,"category_id":1,"batch_no":"RW002","quantity":50,"stain_level":"重","damage_description":"大面积顽固污渍"}')
RECORD_ID2=$(echo $RESULT2 | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID2/sort -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"washing_line_id":1,"work_team_id":1,"sorting_line":"B分拣线","washing_batch_no":"W20240101002"}' > /dev/null
curl -s -X POST $BASE_URL/sorter/cloth-records/$RECORD_ID2/complete-washing -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null

# 创建补洗任务（严重级别）
TASK_RESULT2=$(curl -s -X POST $BASE_URL/inspector/cloth-records/$RECORD_ID2/rewash-tasks -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "reason": "大面积顽固污渍未清除",
  "severity": "严重",
  "expected_completion_time": "2026-06-22T12:00:00",
  "responsible_washing_line_id": 1,
  "responsible_work_team_id": 1
}')
TASK_ID2=$(echo $TASK_RESULT2 | python3 -c "import sys,json; print(json.load(sys.stdin).get('id', 0))")
echo "第二个补洗任务ID: $TASK_ID2"
assert_contains "补洗任务严重程度为严重" "$TASK_RESULT2" "严重"

# 快速走完补洗流程
curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID2/start -H "Authorization: Bearer $SORTER_TOKEN" > /dev/null
curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID2/complete -H "Authorization: Bearer $SORTER_TOKEN" -H "Content-Type: application/json" -d '{"completion_remark": "尝试二次清洗"}' > /dev/null

# 复检结论为继续补洗
RECHECK_RESULT2=$(curl -s -X POST $BASE_URL/inspector/rewash-tasks/$TASK_ID2/recheck -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{
  "cleanliness": "差",
  "damage_recheck": "轻微",
  "final_conclusion": "继续补洗",
  "recheck_remark": "污渍仍有残留，需再次补洗"
}')
echo "第二次复检结果: $RECHECK_RESULT2"
assert_contains "复检结论为继续补洗" "$RECHECK_RESULT2" "继续补洗"

# 验证布草状态回到补洗中
RECORD_STATUS4=$(curl -s $BASE_URL/sorter/cloth-records/$RECORD_ID2 -H "Authorization: Bearer $SORTER_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', ''))")
echo "布草记录当前状态: $RECORD_STATUS4"
assert_contains "继续补洗后布草状态回到补洗中" "$RECORD_STATUS4" "补洗中"
echo ""

echo "=========================================="
echo "  8. 查看布草记录详情（含补洗历史）"
echo "=========================================="
RECORD_DETAIL=$(curl -s $BASE_URL/sorter/cloth-records/$RECORD_ID/detail -H "Authorization: Bearer $SORTER_TOKEN")
echo "布草记录详情关键字段:"
echo "$RECORD_DETAIL" | python3 -c "
import sys,json
data = json.load(sys.stdin)
print(f'  总补洗次数: {data.get(\"total_rewash_count\", 0)}')
print(f'  当前补洗状态: {data.get(\"current_rewash_status\", \"无\")}')
print(f'  补洗任务数量: {len(data.get(\"rewash_tasks\", []))}')
print(f'  补洗历史数量: {len(data.get(\"rewash_history\", []))}')
print(f'  复检历史数量: {len(data.get(\"recheck_history\", []))}')
"

assert_contains "详情包含补洗任务列表" "$RECORD_DETAIL" '"rewash_tasks"'
assert_contains "详情包含补洗历史" "$RECORD_DETAIL" '"rewash_history"'
assert_contains "详情包含复检历史" "$RECORD_DETAIL" '"recheck_history"'
assert_contains "详情包含当前补洗状态" "$RECORD_DETAIL" '"current_rewash_status"'
assert_contains "详情包含总补洗次数" "$RECORD_DETAIL" '"total_rewash_count"'
echo ""

echo "=========================================="
echo "  9. 补洗统计分析测试"
echo "=========================================="

echo "--- 补洗概览统计 ---"
OVERVIEW=$(curl -s $BASE_URL/stats/rewash/overview -H "Authorization: Bearer $ADMIN_TOKEN")
echo "$OVERVIEW" | python3 -c "
import sys,json
data = json.load(sys.stdin)
print(f'  总补洗任务数: {data.get(\"total_rewash_tasks\", 0)}')
print(f'  通过数: {data.get(\"passed_count\", 0)}')
print(f'  未通过数: {data.get(\"failed_count\", 0)}')
print(f'  未完成数: {data.get(\"unfinished_count\", 0)}')
print(f'  补洗通过率: {data.get(\"pass_rate\", 0)}%')
"

echo "--- 按客户维度补洗统计 ---"
BY_CUSTOMER=$(curl -s $BASE_URL/stats/rewash/by-customer -H "Authorization: Bearer $ADMIN_TOKEN")
assert_contains "按客户统计包含第一医院" "$BY_CUSTOMER" "第一医院"

echo "--- 按布草类别维度补洗统计 ---"
BY_CATEGORY=$(curl -s $BASE_URL/stats/rewash/by-category -H "Authorization: Bearer $ADMIN_TOKEN")
assert_contains "按类别统计包含白大褂" "$BY_CATEGORY" "白大褂"

echo "--- 按清洗线维度补洗统计 ---"
BY_LINE=$(curl -s $BASE_URL/stats/rewash/by-washing-line -H "Authorization: Bearer $ADMIN_TOKEN")
assert_contains "按清洗线统计包含1号清洗线" "$BY_LINE" "1号清洗线"

echo "--- 按班组维度补洗统计 ---"
BY_TEAM=$(curl -s $BASE_URL/stats/rewash/by-work-team -H "Authorization: Bearer $ADMIN_TOKEN")
assert_contains "按班组统计包含甲班" "$BY_TEAM" "甲班"

echo "--- 异常补洗排行 ---"
RANKING=$(curl -s $BASE_URL/stats/rewash/abnormal-ranking -H "Authorization: Bearer $ADMIN_TOKEN")
echo "异常补洗排行: $RANKING"
echo ""

echo "=========================================="
echo "  10. 状态流转边界测试"
echo "=========================================="

# 测试对已完成的任务重复启动（应失败）
RESTART_FAIL=$(curl -s -X POST $BASE_URL/sorter/rewash-tasks/$TASK_ID/start -H "Authorization: Bearer $SORTER_TOKEN")
assert_contains "已完成的补洗任务不可重复启动" "$RESTART_FAIL" "不可启动"

# 测试对未完成的任务进行复检（应失败）
RECHECK_FAIL=$(curl -s -X POST $BASE_URL/inspector/rewash-tasks/99999/recheck -H "Authorization: Bearer $INSPECTOR_TOKEN" -H "Content-Type: application/json" -d '{"cleanliness":"良","damage_recheck":"无","final_conclusion":"最终出厂"}')
assert_contains "不存在的补洗任务复检报错" "$RECHECK_FAIL" "不存在"

echo ""

echo "=========================================="
echo "  测试结果汇总"
echo "=========================================="
echo "通过: $PASS"
echo "失败: $FAIL"
if [ $FAIL -eq 0 ]; then
    echo "✅ 全部补洗闭环测试通过！"
else
    echo "❌ 有 $FAIL 个测试失败"
fi
