import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { blogApi } from "../services/blog";

export default function Blog() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    blogApi.listPosts().then((data) => {
      setPosts(data);
      setLoading(false);
    });
  }, []);

  return (
    <div className="blog-page">
      <header className="blog-header">
        <h1>Blog</h1>
      </header>

      {loading && <p>Loading posts...</p>}

      <div className="blog-grid">
        {posts.map((post) => (
          <Link to={`/blog/${post.slug}`} className="blog-card" key={post._id}>
            {post.coverImageUrl && (
              <img src={post.coverImageUrl} alt="" className="blog-card-image" />
            )}
            <div className="blog-card-body">
              <h2>{post.title}</h2>
              {post.excerpt && <p>{post.excerpt}</p>}
              <div className="blog-card-meta">
                {post.authorName} ·{" "}
                {new Date(post.publishedAt).toLocaleDateString()}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
