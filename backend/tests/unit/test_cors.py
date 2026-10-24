from tactix.config import Settings


def test_cors_origins_are_parsed_from_comma_separated_setting():
    settings = Settings(cors_origins="https://studio.example, http://localhost:5173")

    assert settings.cors_origin_list() == [
        "https://studio.example",
        "http://localhost:5173",
    ]


def test_cors_origins_ignore_empty_entries():
    assert Settings(cors_origins="*, , ").cors_origin_list() == ["*"]
