import { sanityClient } from "./sanity";

export const blogApi = {
  listPosts: () =>
    sanityClient.fetch(
      `*[_type == "post"] | order(publishedAt desc) {
        _id,
        title,
        "slug": slug.current,
        excerpt,
        "coverImageUrl": coverImage.asset->url,
        authorName,
        publishedAt
      }`
    ),

  getPostBySlug: (slug) =>
    sanityClient.fetch(
      `*[_type == "post" && slug.current == $slug][0] {
        _id,
        title,
        excerpt,
        "coverImageUrl": coverImage.asset->url,
        authorName,
        publishedAt,
        body
      }`,
      { slug }
    ),
};
