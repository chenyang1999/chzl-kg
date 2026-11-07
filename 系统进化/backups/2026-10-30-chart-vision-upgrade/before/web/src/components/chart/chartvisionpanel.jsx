const BIAS_STYLE = {
  偏多: "text-red-600 bg-red-50",
  偏空: "text-green-700 bg-green-50",
  震荡: "text-amber-700 bg-amber-50",
};

const TYPE_STYLE = {
  突破: "border-red-300 text-red-700",
  低吸: "border-cyan-300 text-cyan-800",
  高抛: "border-amber-300 text-amber-800",
  观望: "border-border text-muted",
  止损: "border-purple-300 text-purple-800",
};

export default function ChartVisionPanel({ result, error, loading }) {
  if (loading) {
    return (
      <div className="border border-border rounded-lg p-4 text-sm text-muted animate-pulse">
        Agent 正在结合多周期图表与量价结构生成买卖点…
      </div>
    );
  }
  if (error) {
    return <div className="border border-red-200 rounded-lg p-4 text-sm text-red-600">{error}</div>;
  }
  if (!result) return null;

  const bias = result.bias || "震荡";
  const signals = result.signals || [];

  return (
    <div className="border border-border rounded-lg p-4 space-y-3 bg-card">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">Agent 看盘结论</span>
        <span className={`text-xs px-2 py-0.5 rounded ${BIAS_STYLE[bias] || BIAS_STYLE.震荡}`}>
          {bias}
        </span>
        {result.confidence != null && (
          <span className="text-xs text-muted">置信度 {(result.confidence * 100).toFixed(0)}%</span>
        )}
      </div>

      {result.summary && <p className="text-sm leading-relaxed">{result.summary}</p>}

      {signals.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-muted">买卖点建议</div>
          {signals.map((s, i) => (
            <div
              key={i}
              className={`text-xs border rounded-lg px-3 py-2 ${TYPE_STYLE[s.type] || TYPE_STYLE.观望}`}
            >
              <div className="flex flex-wrap gap-2 items-center mb-1">
                <span className="font-semibold">{s.type || "观望"}</span>
                {s.period && <span className="text-muted">{s.period}</span>}
                {s.price_hint != null && <span>参考价 {s.price_hint}</span>}
                {s.confidence != null && (
                  <span className="text-muted">{(s.confidence * 100).toFixed(0)}%</span>
                )}
              </div>
              {s.reason && <p className="text-muted leading-snug">{s.reason}</p>}
            </div>
          ))}
        </div>
      )}

      {result.risks?.length > 0 && (
        <div className="text-xs text-muted">
          <span className="font-medium">风险：</span>
          {result.risks.join("；")}
        </div>
      )}

      {result.action && (
        <div className="text-sm border-t border-border pt-2">
          <span className="font-medium">操作建议：</span>
          {result.action}
        </div>
      )}

      {result.disclaimer && (
        <p className="text-[10px] text-muted">{result.disclaimer}</p>
      )}
    </div>
  );
}
