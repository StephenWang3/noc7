

def test_html_entities_in_the_source_match_their_decoded_characters():
    # 邮件原文常带 HTML 实体，模型摘录时会写成解码后的字符；位置仍指向原文。
    from noc7.quote_match import match_quote
    source = "Service was impacted in our supplier&#39;s nid.\n<br>&#22238;&#22797;：A &gt; B"
    check = match_quote("in our supplier's nid.", source)
    assert check.status == "whitespace" and check.original == "in our supplier&#39;s nid."
    assert source[check.start:check.end] == check.original
    assert match_quote("回复：A > B", source).original == "&#22238;&#22797;：A &gt; B"
    assert match_quote("supplier&#39;s", source).status == "strict"
    assert match_quote("supplier‘s", source).status == "mismatch"
