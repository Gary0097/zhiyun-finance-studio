(function () {
  var Q = window.QwenPaw;
  if (!Q || !Q.host || !Q.host.React || !Q.registerRoutes) return;
  var React = Q.host.React, antd = Q.host.antd, h = React.createElement;
  function request(path, body) {
    return Q.host.fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }).then(function (response) {
      return response.json().then(function (data) { if (!response.ok) throw new Error(data.detail || "操作失败"); return data; });
    });
  }
  function FinanceStudio() {
    var invoiceTextState = React.useState(""), invoiceText = invoiceTextState[0], setInvoiceText = invoiceTextState[1];
    var invoiceResultState = React.useState(null), invoiceResult = invoiceResultState[0], setInvoiceResult = invoiceResultState[1];
    var financeTextState = React.useState(""), financeText = financeTextState[0], setFinanceText = financeTextState[1];
    var financeResultState = React.useState(null), financeResult = financeResultState[0], setFinanceResult = financeResultState[1];
    var costTextState = React.useState(""), costText = costTextState[0], setCostText = costTextState[1];
    var costResultState = React.useState(null), costResult = costResultState[0], setCostResult = costResultState[1];
    var reviewerState = React.useState(""), reviewer = reviewerState[0], setReviewer = reviewerState[1];
    var recentState = React.useState([]), recent = recentState[0], setRecent = recentState[1];
    var loadingState = React.useState(false), loading = loadingState[0], setLoading = loadingState[1];
    var message = antd.App.useApp().message;
    function parseJson(text, label, object) {
      var parsed;
      try { parsed = JSON.parse(text); } catch (err) { message.error(label + "必须是" + (object ? "JSON对象" : "JSON数组")); return null; }
      if (object) {
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) { message.error(label + "必须是JSON对象"); return null; }
      } else if (!Array.isArray(parsed) || !parsed.length) { message.warning("请提供至少一条" + label); return null; }
      return parsed;
    }
    function loadRecent() {
      return Q.host.fetch("/zhiyun-finance-studio/artifacts").then(function (response) { return response.json(); })
        .then(function (data) { setRecent(data.artifacts || []); }).catch(function () {});
    }
    function runInvoice() {
      var invoices = parseJson(invoiceText, "发票");
      if (!invoices) return;
      setLoading(true);
      request("/zhiyun-finance-studio/artifacts/expense", { invoices: invoices }).then(function (data) { setInvoiceResult(data); message.success("已生成报销审核工件，等待审阅"); loadRecent(); })
        .catch(function (e) { message.error(e.message); }).finally(function () { setLoading(false); });
    }
    function runFinance() {
      var records = parseJson(financeText, "财务记录");
      if (!records) return;
      setLoading(true);
      request("/zhiyun-finance-studio/artifacts/finance", { records: records }).then(function (data) { setFinanceResult(data); message.success("已生成财务看板工件，等待审阅"); loadRecent(); })
        .catch(function (e) { message.error(e.message); }).finally(function () { setLoading(false); });
    }
    function runCost() {
      var parameters = parseJson(costText, "成本参数", true);
      if (!parameters) return;
      setLoading(true);
      request("/zhiyun-finance-studio/artifacts/cost", { parameters: parameters }).then(function (data) { setCostResult(data); message.success("已生成成本预测工件，等待审阅"); loadRecent(); })
        .catch(function (e) { message.error(e.message); }).finally(function () { setLoading(false); });
    }
    function decide(kind, action) {
      if (!reviewer.trim()) { message.warning("请输入审阅人"); return; }
      var result = kind === "expense" ? invoiceResult : kind === "finance" ? financeResult : costResult;
      if (!result) { message.warning("请先生成工件"); return; }
      request("/zhiyun-finance-studio/artifacts/" + result.id + "/reviews", { action: action, reviewer: reviewer }).then(function (data) {
        if (kind === "expense") setInvoiceResult(data); else if (kind === "finance") setFinanceResult(data); else setCostResult(data);
        message.success(action === "accept" ? "工件已接受" : "工件已驳回"); loadRecent();
      }).catch(function (e) { message.error(e.message); });
    }
    function exportArtifact(result) {
      if (!result) return;
      window.open("/zhiyun-finance-studio/artifacts/" + result.id + "/export", "_blank");
    }
    function reviewRow(result, kind, title) {
      return h("div", { style: { display: "flex", gap: 8, marginTop: 12 } },
        h(antd.Input, { value: reviewer, onChange: function (e) { setReviewer(e.target.value); }, placeholder: "审阅人", style: { width: 180 } }),
        h(antd.Button, { type: "primary", onClick: function () { decide(kind, "accept"); } }, "接受"),
        h(antd.Button, { danger: true, onClick: function () { decide(kind, "reject"); } }, "驳回"),
        h(antd.Button, { disabled: result.status !== "accepted", onClick: function () { exportArtifact(result); } }, "导出")
      );
    }
    var invoiceExample = '[{"invoice_no":"INV-2026-081","invoice_date":"2026-08-10","amount":5200,"tax_amount":676,"tax_rate":0.13,"supplier":"新华印刷","description":"差旅机票住宿","tax_payer_number":"91440101"}]';
    var financeExample = '[{"month":"2026-06","revenue":1200,"cost":720,"operating_expense":180,"current_assets":600,"current_liabilities":300,"total_assets":1000,"total_liabilities":400},{"month":"2026-07","revenue":1320,"cost":770,"operating_expense":190,"current_assets":660,"current_liabilities":310,"total_assets":1050,"total_liabilities":410}]';
    var costExample = '{"product":"压铸件","current_unit_cost":12.5,"volume":12000,"labor_share":0.15,"overhead_share":0.15,"materials":[{"name":"铝合金","share":0.6,"price_change_pct":0.08}]}';
    var intents = [
      { key: "expense", label: "报销审核" },
      { key: "finance", label: "财务看板" },
      { key: "cost", label: "成本预测" }
    ];
    var activeState = React.useState("expense"), active = activeState[0], setActive = activeState[1];
    React.useEffect(function () { loadRecent(); }, []);
    return h("div", { style: { padding: 28, height: "100%", overflow: "auto", background: "#f7f8fa" } }, h("div", { style: { maxWidth: 1080, margin: "0 auto" } },
      h("h2", null, "智能财务中心"), h("p", { style: { color: "#667085" } }, "发票报销审核、财务比率看板、原材料价格变动下的成本预测。"),
      h(antd.Tabs, { activeKey: active, onChange: setActive, items: intents.map(function (item) {
        return { key: item.key, label: item.label, children: item.key === "expense" ? (
          h("div", null,
            h(antd.Alert, { type: "info", showIcon: true, message: "报销审核", description: "粘贴发票JSON数组，每项含 invoice_no、invoice_date、amount、tax_amount、tax_rate、supplier、description、tax_payer_number。" }),
            h(antd.Input.TextArea, { style: { marginTop: 12 }, value: invoiceText, rows: 8, onChange: function (e) { setInvoiceText(e.target.value); }, placeholder: invoiceExample }),
            h(antd.Button, { type: "primary", loading: loading, style: { marginTop: 12 }, onClick: runInvoice }, "审核并生成工件"),
            invoiceResult ? h("div", null,
              h(antd.Row, { gutter: 16, style: { marginTop: 16 } },
                ["通过", "退回补正", "驳回", "总金额"].map(function (label, index) {
                  var value = [invoiceResult.payload.summary.passed, invoiceResult.payload.summary.returned, invoiceResult.payload.summary.rejected, invoiceResult.payload.summary.total_amount][index];
                  return h(antd.Col, { span: 6, key: label }, h(antd.Card, { size: "small" }, h(antd.Statistic, { title: label, value: value, precision: index === 3 ? 2 : 0 })));
                })
              ),
              h(antd.Card, { size: "small", title: "审核明细", style: { marginTop: 12 } },
                h(antd.Table, { size: "small", rowKey: "invoice_no", dataSource: invoiceResult.payload.items, pagination: { pageSize: 8 }, columns: [
                  { title: "发票号", dataIndex: "invoice_no" }, { title: "供应商", dataIndex: "supplier" },
                  { title: "金额", dataIndex: "amount" }, { title: "类型", dataIndex: "expense_type" },
                  { title: "状态", dataIndex: "status", render: function (v) { return h(antd.Tag, { color: v === "通过" ? "green" : v === "退回补正" ? "orange" : "red" }, v); } },
                  { title: "问题", dataIndex: "checks", render: function (v) { return (v || []).length ? v.map(function (c) { return c.message; }).join("；") : "无"; } }
                ] })
              ),
              reviewRow(invoiceResult, "expense", "报销审核工件")
            ) : null
          )
        ) : item.key === "finance" ? (
          h("div", null,
            h(antd.Alert, { type: "info", showIcon: true, message: "财务看板", description: "粘贴财务JSON数组，每项含 month、revenue、cost、operating_expense、current_assets、current_liabilities、total_assets、total_liabilities。" }),
            h(antd.Input.TextArea, { style: { marginTop: 12 }, value: financeText, rows: 8, onChange: function (e) { setFinanceText(e.target.value); }, placeholder: financeExample }),
            h(antd.Button, { type: "primary", loading: loading, style: { marginTop: 12 }, onClick: runFinance }, "分析并生成工件"),
            financeResult ? h("div", null,
              h(antd.Row, { gutter: 16, style: { marginTop: 16 } },
                ["毛利率", "净利率", "经营利润率", "流动比率"].map(function (label, index) {
                  var value = [financeResult.payload.summary.gross_margin, financeResult.payload.summary.net_margin, financeResult.payload.summary.operating_margin, financeResult.payload.summary.current_ratio][index];
                  return h(antd.Col, { span: 6, key: label }, h(antd.Card, { size: "small" }, h(antd.Statistic, { title: label, value: value, suffix: index < 3 ? "%" : "", precision: 1 })));
                })
              ),
              h(antd.Card, { size: "small", title: "财务记录", style: { marginTop: 12 } },
                h(antd.Table, { size: "small", rowKey: "month", dataSource: financeResult.payload.periods, pagination: { pageSize: 8 }, columns: [
                  { title: "月份", dataIndex: "month" }, { title: "营收", dataIndex: "revenue" },
                  { title: "毛利率", dataIndex: "gross_margin", render: function (v) { return v + "%"; } },
                  { title: "净利率", dataIndex: "net_margin", render: function (v) { return v + "%"; } },
                  { title: "流动比率", dataIndex: "current_ratio", render: function (v) { return v === null ? "-" : v; } },
                  { title: "负债率", dataIndex: "debt_ratio", render: function (v) { return v + "%"; } }
                ] })
              ),
              reviewRow(financeResult, "finance", "财务分析工件")
            ) : null
          )
        ) : (
          h("div", null,
            h(antd.Alert, { type: "info", showIcon: true, message: "成本预测", description: "粘贴成本JSON对象，含 current_unit_cost、volume、labor_share、overhead_share 与 materials(share/price_change_pct)。" }),
            h(antd.Input.TextArea, { style: { marginTop: 12 }, value: costText, rows: 8, onChange: function (e) { setCostText(e.target.value); }, placeholder: costExample }),
            h(antd.Button, { type: "primary", loading: loading, style: { marginTop: 12 }, onClick: runCost }, "预测并生成工件"),
            costResult ? h("div", null,
              h(antd.Row, { gutter: 16, style: { marginTop: 16 } },
                ["原单位成本", "新单位成本", "变动%", "年度影响"].map(function (label, index) {
                  var value = [costResult.payload.old_unit_cost, costResult.payload.new_unit_cost, costResult.payload.unit_cost_change_pct, costResult.payload.annual_saving][index];
                  return h(antd.Col, { span: 6, key: label }, h(antd.Card, { size: "small" }, h(antd.Statistic, { title: label, value: value, precision: 2 })));
                })
              ),
              h(antd.Card, { size: "small", title: "物料拆解", style: { marginTop: 12 } },
                h(antd.Table, { size: "small", rowKey: "name", dataSource: costResult.payload.materials, pagination: false, columns: [
                  { title: "物料", dataIndex: "name" }, { title: "占比", dataIndex: "share" },
                  { title: "价格变动", dataIndex: "price_change_pct", render: function (v) { return v + "%"; } },
                  { title: "原成本", dataIndex: "base_cost" }, { title: "新成本", dataIndex: "new_cost" }
                ] })
              ),
              reviewRow(costResult, "cost", "成本预测工件")
            ) : null
          )
        )};
      }) }
    )));
  }
  Q.registerRoutes("zhiyun-finance-studio", [{ path: "/apps/zhiyun-finance-studio", component: FinanceStudio, label: "智能财务中心", icon: "💹", priority: 80 }]);
})();
