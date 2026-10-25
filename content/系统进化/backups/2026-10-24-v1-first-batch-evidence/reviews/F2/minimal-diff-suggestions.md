# F2 最小修改建议（只建议，未应用）

## F2-01：绑定扫描日期，不造年龄阈值

影响点：`session_context.py:62`、`_buy_common.py:82`、`qmt_context.py:296`。保留现有价格/RR/扫描动作/权限与卖出分离。

```diff
-def buy_allowed(ts_code: str, *, entry_style: str = "pullback") -> tuple[bool, list[str]]:
+def buy_allowed(ts_code: str, *, entry_style: str = "pullback", trade_date: str) -> tuple[bool, list[str]]:
+    if _SESSION["scan_meta"].get("trade_date") != trade_date:
+        return False, ["scan_date_missing_or_mismatch"]
     opp = get_opportunity(ts_code)
```

两个订单消费者必须显式传入已验证日期：

```diff
-        scan_ok, scan_reasons = buy_allowed(ts_code, entry_style=rule_type)
+        scan_ok, scan_reasons = buy_allowed(ts_code, entry_style=rule_type,
+                                            trade_date=qmt_ctx.trade_date)
```

```diff
-            if not buy_allowed(ts_code, entry_style=rule_type)[0]:
+            if not buy_allowed(ts_code, entry_style=rule_type,
+                               trade_date=self.trade_date)[0]:
```

更新其他明确调用者的合成fixture提供真实明确日期，不将日期缺失补为系统今日；不要静默允许旧调用者继续绕过新合同。`run_load_plan(dispatch=True)`没有新扫描时可拒买，不能复用异日成功行。正常watcher仍保留clear→本轮scan→set→dispatch；不要求新增行情调用。

## F2-02：最终sell至少绑定bid；不要借此重造退出策略

`qmt_context.py:154-161`已有有效side book检查后、Amygdala前追加：

```diff
+        if side == "sell" and limit_price != book_price:
+            record.update(status="rejected", reason="sell_limit_not_authorized")
+            append_jsonl(self.orders_path, record)
+            return record
```

这复用当前所有正常sell wrapper本就使用bid的合同，不暗设滑点或其他阈值。

关于未触发stop与10%规则被低层改量：当前生产订单调用者仅两个common wrapper；正常live卖出wrapper已做触发/算量，F2实测未触发stop不下单。此缺口I1之前已存在，不能写成新增实盘误卖。若本次验收目标确实包括“低层直调也只能执行精确已授权订单”，最小下一步是在现有wrapper→context接口传递并绑定**具体规则选择、核验通过的数量与报价**，最终对精确意图复核；不能只用rule_type充当整份订单许可，也不应仅凭通用predicate重写委托给watcher的复杂退出条件。

本F2不实施该接口设计、不新增退出策略或权限。若本次只承诺共同许可/退出名单/kill/bid存在/available，不承诺低层重验触发与规则量，应明确收窄安全声明并继续保留不能实盘放行结论。

## 不应做的“修复”

- 不删`ExecutionAuthorization.validated_plan:125-128`给明确整份no_trade/unready计划补live许可。I1之前loader已有整份限制合同。
- 不将`no_trade_conditions`等买入门禁套到sell；本轮正向live卖出证据已证明该分离正常。
- 不用本次修改处理跨进程原子性、券商身份/在途成交撤单对账，或发明报价龄阈值；它们仍是既知实盘阻断边界。
