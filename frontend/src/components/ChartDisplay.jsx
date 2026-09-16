import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import { Line, Bar, Pie } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

export default function ChartDisplay({ chartData }) {
  if (!chartData || !chartData.type || !chartData.data) {
    return null;
  }

  const renderChart = () => {
    const { type, data, config } = chartData;

    // Default configuration
    const defaultConfig = {
      responsive: true,
      maintainAspectRatio: false,
      ...config
    };

    switch (type) {
      case 'line':
        return <Line data={data} options={defaultConfig} />;
      case 'bar':
        return <Bar data={data} options={defaultConfig} />;
      case 'pie':
        return <Pie data={data} options={defaultConfig} />;
      case 'candlestick':
        // For candlestick, we'll use a line chart as fallback
        return <Line data={data} options={defaultConfig} />;
      default:
        return <Line data={data} options={defaultConfig} />;
    }
  };

  return (
    <div className="chart-container">
      {chartData.title && (
        <h4 className="chart-title">{chartData.title}</h4>
      )}
      <div className="chart-wrapper" style={{ height: '300px', width: '100%' }}>
        {renderChart()}
      </div>
    </div>
  );
}