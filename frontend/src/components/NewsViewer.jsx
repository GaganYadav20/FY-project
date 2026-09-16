import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import './NewsViewer.css';

const NewsViewer = () => {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = async (e) => {
    e.preventDefault();
    
    if (!searchQuery.trim()) {
      setError('Please enter a search query');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiClient.get(`/news/search?q=${encodeURIComponent(searchQuery)}&limit=50`);
      
      if (response.data.success) {
        setNews(response.data.articles || []);
      } else {
        console.log('API returned error:', response.data.error);
        setError(response.data.error || 'Search failed');
      }
    } catch (err) {
      console.error('Error searching news:', err);
      console.error('Error response:', err.response?.data);
      setError(err.response?.data?.detail || 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 60) {
      return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
      return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    } else {
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric' 
      });
    }
  };

  return (
    <div className="news-viewer">
      <div className="news-header">
        <h1>📰 Financial News Search</h1>
        <p className="news-subtitle">Search global financial news</p>
        <p className="news-hint">💡 Use stock symbols (AAPL, TSLA, MSFT, INFY) or broad keywords (AI, technology, crypto)</p>
      </div>

      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          placeholder="Search financial news (e.g., AAPL, INFY, AI, crypto, technology)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
        <button type="submit" className="search-button">
          🔍 Search
        </button>
      </form>

      {error && (
        <div className="news-error">
          <p>⚠️ {error}</p>
          {error.includes('API key') && (
            <p className="error-hint">
              To enable financial news, add your Finnhub API key to backend/.env:
              <br />
              <code>FINNHUB_API_KEY=your_key_here</code>
              <br />
              Get a free API key at: <a href="https://finnhub.io/register" target="_blank" rel="noopener noreferrer">https://finnhub.io/register</a>
              <br />
              Free tier: 60 API calls/minute
            </p>
          )}
        </div>
      )}

      {loading ? (
        <div className="news-loading">
          <div className="loading-spinner"></div>
          <p>Loading financial news...</p>
        </div>
      ) : (
        <div className="news-list">
          {news.length === 0 ? (
            <div className="no-news">
              <p>� No news articles found for "{searchQuery}"</p>
              <p className="hint">Try these working examples:</p>
              <p className="examples">
                <strong>Stock Symbols:</strong> AAPL, TSLA, MSFT, GOOGL, INFY<br/>
                <strong>Keywords:</strong> AI, crypto, technology, merger, earnings
              </p>
            </div>
          ) : (
            news.map((article) => (
              <div key={article.id} className="news-article">
                {article.image_url && (
                  <div className="article-image">
                    <img src={article.image_url} alt={article.title} />
                  </div>
                )}
                
                <div className="article-content">
                  <div className="article-header">
                    <h2 className="article-title">
                      <a href={article.url} target="_blank" rel="noopener noreferrer">
                        {article.title}
                      </a>
                    </h2>
                  </div>

                  <p className="article-description">
                    {article.description || article.snippet}
                  </p>

                  {article.related_symbols && article.related_symbols.length > 0 && (
                    <div className="article-entities">
                      {article.related_symbols.slice(0, 5).map((symbol, idx) => (
                        <span key={idx} className="entity-tag">
                          {symbol}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="article-footer">
                    <span className="article-source">
                      📰 {article.source}
                    </span>
                    <span className="article-date">
                      🕒 {formatDate(article.published_at)}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default NewsViewer;
