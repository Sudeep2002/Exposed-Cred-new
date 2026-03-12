from datetime import timedelta

def get_reference_date(current_df):
    return current_df["exposure_date"].max()


def calculate_password_reset_candidates(current_df, master_df):
    ref_date = get_reference_date(current_df)
    six_months_ago = ref_date - timedelta(days=183)

    recent_exposed = master_df[
        master_df["last_exposed_date"] >= six_months_ago
    ]["email"]

    reset_df = current_df[
        ~current_df["email"].isin(recent_exposed)
    ]

    return reset_df


def get_password_reset_count(current_df, master_df):
    return len(calculate_password_reset_candidates(current_df, master_df))


def get_recently_exposed_users(current_df, master_df):
    ref_date = get_reference_date(current_df)
    six_months_ago = ref_date - timedelta(days=183)

    return master_df[
        master_df["last_exposed_date"] >= six_months_ago
    ]


def get_exposure_breakdown_by_source(recent_df):
    return recent_df.groupby("source").size().to_dict()
