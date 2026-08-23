# 智造云智能财务中心

独立 PawApp。基于真实发票与财务数据完成报销智能审核、财务比率看板和原材料价格变动下的成本预测，所有结果进入可审阅工件等待人工确认。

## 验证

```bash
python -m unittest discover -s tests -v
python -m py_compile backend/main.py backend/finance_engine.py backend/finance_workflow.py
node --check ui/index.js
```
