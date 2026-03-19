import SwiftUI

struct StoryTab: View {
    let story: BuildingStory?

    var body: some View {
        if let story {
            VStack(alignment: .leading, spacing: 16) {
                Text(story.headline ?? "")
                    .font(.system(size: 18, weight: .bold))

                Text(story.narrative ?? "")
                    .font(.system(size: 15))
                    .foregroundColor(.secondary)
                    .lineSpacing(4)

                if let facts = story.funFacts, !facts.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Fun Facts")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(.green)

                        ForEach(facts, id: \.self) { fact in
                            HStack(alignment: .top, spacing: 8) {
                                Text("\u{2022}")
                                    .foregroundColor(.green)
                                Text(fact)
                                    .font(.system(size: 14))
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding(12)
                    .background(Color(.systemGray6))
                    .cornerRadius(10)
                }
            }
        } else {
            VStack(spacing: 8) {
                Image(systemName: "book.closed")
                    .font(.system(size: 32))
                    .foregroundColor(.secondary)
                Text("No story available yet")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.top, 40)
        }
    }
}
