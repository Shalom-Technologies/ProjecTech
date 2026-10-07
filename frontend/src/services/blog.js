const SITE = "257818724";
const BASE = `https://public-api.wordpress.com/rest/v1.1/sites/${SITE}`;

// Turns HTML (titles, excerpts) into plain text
function toText(html = "") {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return (doc.body.textContent || "").trim();
}

function normalize(p) {
  return {
    id: p.ID,
    title: toText(p.title),
    slug: p.slug,
    excerpt: toText(p.excerpt),
    coverImageUrl: p.featured_image || null,
    authorName: p.author?.name || "",
    publishedAt: p.date,
    contentHtml: p.content,
  };
}

async function listPosts() {
  const res = await fetch(`${BASE}/posts?number=50&order_by=date&order=DESC`);
  if (!res.ok) throw new Error("Failed to load posts");
  const data = await res.json();
  return data.posts.map(normalize);
}

async function getPostBySlug(slug) {
  const res = await fetch(`${BASE}/posts/slug:${encodeURIComponent(slug)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to load post");
  return normalize(await res.json());
}

export const blogApi = { listPosts, getPostBySlug };
