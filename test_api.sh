#!/bin/bash

BASE_URL="http://localhost:8144"

echo "=== 1. 管理员登录 ==="
ADMIN_TOKEN=$(curl -s -X POST $BASE_URL/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "管理员 Token: $ADMIN_TOKEN"

echo ""
echo "=== 2. 创建客户单位 ==="
curl -s -X POST $BASE_URL/customers/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"第一人民医院","contact":"张主任","phone":"13800138001","address":"北京市朝阳区"}'
echo ""

echo ""
echo "=== 3. 创建布草类别 ==="
curl -s -X POST $BASE_URL/cloth-categories/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"白大褂","description":"医生工作服"}'
echo ""

echo ""
echo "=== 4. 创建清洗线 ==="
curl -s -X POST $BASE_URL/washing-lines/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"1号清洗线","capacity":500}'
echo ""

echo ""
echo "=== 5. 创建责任班组 ==="
curl -s -X POST $BASE_URL/work-teams/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"甲班","leader":"李组长"}'
echo ""

echo ""
echo "=== 6. 分拣员登录 ==="
SORTER_TOKEN=$(curl -s -X POST $BASE_URL/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"sorter","password":"sorter123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "分拣员 Token: $SORTER_TOKEN"

echo ""
echo "=== 7. 登记布草入厂 ==="
curl -s -X POST $BASE_URL/sorter/cloth-records \
  -H "Authorization: Bearer $SORTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":1,"category_id":1,"batch_no":"B20240101001","quantity":100,"stain_level":"中","damage_description":"轻微污渍"}'
echo ""

echo ""
echo "=== 8. 测试同一批号重复入厂校验 ==="
curl -s -X POST $BASE_URL/sorter/cloth-records \
  -H "Authorization: Bearer $SORTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":1,"category_id":1,"batch_no":"B20240101001","quantity":50,"stain_level":"轻"}'
echo ""

echo ""
echo "=== 9. 分拣布草 ==="
curl -s -X POST $BASE_URL/sorter/cloth-records/1/sort \
  -H "Authorization: Bearer $SORTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cloth_record_id":1,"washing_line_id":1,"work_team_id":1}'
echo ""

echo ""
echo "=== 10. 质检员登录 ==="
INSPECTOR_TOKEN=$(curl -s -X POST $BASE_URL/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"inspector","password":"inspector123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "质检员 Token: $INSPECTOR_TOKEN"

echo ""
echo "=== 11. 质检记录 ==="
curl -s -X POST $BASE_URL/inspector/cloth-records/1/qc \
  -H "Authorization: Bearer $INSPECTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cloth_record_id":1,"cleanliness":"良","damage_recheck":"轻微","rewash_conclusion":false,"delivery_suggestion":"同意出厂"}'
echo ""

echo ""
echo "=== 12. 获取布草记录详情 ==="
curl -s $BASE_URL/sorter/cloth-records/1 \
  -H "Authorization: Bearer $SORTER_TOKEN" | python3 -m json.tool

echo ""
echo "=== 13. 统计摘要 ==="
curl -s $BASE_URL/stats/summary \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

echo ""
echo "=== 14. 异常检测 ==="
curl -s $BASE_URL/anomalies/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
