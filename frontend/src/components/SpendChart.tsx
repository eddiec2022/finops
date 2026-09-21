import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SpendChartPoint } from "../lib/combineSpendSeries";
import { formatCurrency } from "../lib/formatCurrency";

const TEAL = "#0F6E56";

function formatDateTick(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatDateLabel(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
}

export function SpendChart({ data }: { data: SpendChartPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#EDE6DC" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={formatDateTick}
          tick={{ fontSize: 12, fill: "#78716C" }}
          axisLine={false}
          tickLine={false}
          minTickGap={32}
        />
        <YAxis
          tickFormatter={(value: number) => formatCurrency(value, { compact: true })}
          tick={{ fontSize: 12, fill: "#78716C" }}
          axisLine={false}
          tickLine={false}
          width={56}
        />
        <Tooltip
          formatter={(value: number, name: string) => [formatCurrency(value), name === "actual" ? "Actual" : "Projected"]}
          labelFormatter={formatDateLabel}
          contentStyle={{ borderRadius: 8, border: "1px solid #E7E0D4", fontSize: 13 }}
        />
        <Line
          type="monotone"
          dataKey="actual"
          name="actual"
          stroke={TEAL}
          strokeWidth={2.5}
          dot={false}
          connectNulls={false}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="projected"
          name="projected"
          stroke={TEAL}
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={false}
          connectNulls={false}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
