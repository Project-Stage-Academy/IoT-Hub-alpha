def assert_pagination_envelope(payload):
    assert "data" in payload
    assert "pagination" in payload
    pagination = payload["pagination"]
    assert "page" in pagination
    assert "page_size" in pagination
    assert "total" in pagination
    assert "total_pages" in pagination
    assert "next_page" in pagination
    assert "prev_page" in pagination
