import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import DOMPurify from "dompurify";
import { blogApi } from "../services/blog";

export default function BlogPost() {
  const { slug } = useParams();
  const [post, setPost] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    setPost(null);
    setNotFound(false);
    setError(false);
    blogApi
      .getPostBySlug(slug)
      .then((data) => {
        if (!data) setNotFound(true);
        else setPost(data);
      })
      .catch(() => setError(true));
  }, [slug]);

  if (notFound || error) {
    return (
      <div className="blog-page">
        <p>{notFound ? "Post not found." : "Couldn't load this post right now."}</p>
        <Link to="/blog">← Back to blog</Link>
      </div>
    );
  }

  if (!post) return null;

  return (
    <article className="blog-post">
      <Link to="/blog" className="back-link">
        ← Back to blog
      </Link>

      {post.coverImageUrl && (
        <img src={post.coverImageUrl} alt="" className="blog-post-cover" />
      )}

      <h1>{post.title}</h1>
      <div className="blog-post-meta">
        {post.authorName} · {new Date(post.publishedAt).toLocaleDateString()}
      </div>

      <div
        className="blog-post-body"
        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(post.contentHtml) }}
      />
    </article>
  );
}
