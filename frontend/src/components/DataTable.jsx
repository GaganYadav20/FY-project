import React from 'react';

export default function DataTable({ structuredData }) {
  if (!structuredData || !structuredData.data) {
    return null;
  }

  const { title, data, type } = structuredData;
  const { rows, columns } = data;

  if (!rows || !Array.isArray(rows) || rows.length === 0) {
    return null;
  }

  // Helper function to determine value styling
  const getValueClass = (value, key) => {
    if (typeof value !== 'string') return '';
    
    // Check for percentage or currency changes
    if (key === 'value' && (value.includes('%') || value.includes('₹'))) {
      if (value.includes('-') || value.includes('(')) {
        return 'value-negative';
      } else if (value.includes('+') || (value.includes('₹') && !value.includes('-'))) {
        return 'value-positive';
      }
    }
    
    return '';
  };

  return (
    <div className="data-table-container" data-type={type}>
      {title && <h4 className="data-table-title">{title}</h4>}
      <div className="data-table-wrapper">
        <table className="data-table">
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="data-table-row">
                {columns ? (
                  columns.map((col) => (
                    <td 
                      key={col} 
                      className={`data-table-cell data-table-${col} ${getValueClass(row[col], col)}`}
                    >
                      {row[col]}
                    </td>
                  ))
                ) : (
                  Object.values(row).map((value, colIndex) => (
                    <td key={colIndex} className="data-table-cell">
                      {value}
                    </td>
                  ))
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}