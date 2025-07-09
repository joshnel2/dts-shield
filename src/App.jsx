import React, { useState } from 'react';
import { encryptData, checkLLMRisk } from './shield';
import './App.css';

function App() {
  const [query, setQuery] = useState('');
  const [alert, setAlert] = useState('');
  const [insights] = useState([{ id: 1, item: 'Top Purchase', value: '$500' }]);

  const handleQuery = async () => {
    if (!query) return;
    const encrypted = encryptData(query);
    const risk = await checkLLMRisk(encrypted);
    setAlert(risk);
  };

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <h1 className="text-3xl font-bold text-center mb-6">DTS Privacy Shield</h1>
      <div className="max-w-md mx-auto bg-white p-6 rounded-lg shadow-md">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter customer query"
          className="w-full p-2 border rounded mb-4"
        />
        <button
          onClick={handleQuery}
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
        >
          Check Privacy
        </button>
        {alert && (
          <div className={`mt-4 p-2 rounded ${alert.includes('Unauthorized') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
            {alert}
          </div>
        )}
        <h2 className="mt-6 text-xl font-semibold">Secure Insights</h2>
        <table className="w-full mt-2 border">
          <thead>
            <tr className="bg-gray-200">
              <th className="p-2">Item</th>
              <th className="p-2">Value</th>
            </tr>
          </thead>
          <tbody>
            {insights.map((insight) => (
              <tr key={insight.id} className="border-t">
                <td className="p-2">{insight.item}</td>
                <td className="p-2">{insight.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default App;
