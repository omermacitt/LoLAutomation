use regex::Regex;
use serde::Deserialize;
use std::sync::OnceLock;

#[derive(Deserialize)]
struct Rule {
    method: String,
    pattern: String,
    image: bool,
}

pub fn allowed(method: &str, path: &str, image_only: bool) -> bool {
    if path.len() > 2048 || path.contains(['?', '#', '%', '\\']) {
        return false;
    }
    static RULES: OnceLock<Vec<(Rule, Regex)>> = OnceLock::new();
    let rules = RULES.get_or_init(|| {
        let values: Vec<Rule> = serde_json::from_str(include_str!(
            "../../../src/rune_pilot/composition/desktop_routes.json"
        ))
        .expect("packaged desktop route policy");
        values
            .into_iter()
            .map(|rule| {
                let regex = Regex::new(&format!("^(?:{})$", rule.pattern)).unwrap();
                (rule, regex)
            })
            .collect()
    });
    rules.iter().any(|(rule, pattern)| {
        rule.method == method && (!image_only || rule.image) && pattern.is_match(path)
    })
}

#[cfg(test)]
mod tests {
    use super::allowed;

    #[test]
    fn commands_and_assets_have_separate_narrow_routes() {
        assert!(allowed("PUT", "/settings", false));
        assert!(!allowed("PUT", "/settings", true));
        assert!(allowed("GET", "/champions/266/portrait", true));
        assert!(allowed("GET", "/champions/266/skins/266001/artwork", true));
        for path in [
            "/accounts",
            "/login-jobs/active",
            "/league/launch",
            "/updates",
            "/docs",
            "https://example.com",
            "/%68ealth",
            "/health?x=1",
            "/champions/0/portrait",
        ] {
            assert!(!allowed("GET", path, false), "{path}");
        }
        assert!(!allowed("POST", "/champions/266/portrait", false));
    }
}
