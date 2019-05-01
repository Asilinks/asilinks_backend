# Model imports
from .documents import Article

def get_blog_statistics():
  total_articles = Article.objects.all()
  return {
      "published": len([
          article for article in total_articles
          if not article.draft and article.active
      ]),
      "non_published": len([
          article for article in total_articles
          if not article.draft and not article.active
      ]),
      "draft": len([
          article for article in total_articles
          if article.draft
      ]),
  }
