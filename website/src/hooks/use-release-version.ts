import { useQuery } from "@tanstack/react-query";

// Share the published package version between the hero and footer.
export function useReleaseVersion() {
  const { data } = useQuery({
    queryKey: ["release-version"],
    queryFn: async ({ signal }) => {
      const response = await fetch("https://pypi.org/pypi/codegraphcontext/json", { signal });
      if (!response.ok) throw new Error("Failed to fetch release version");

      const data = await response.json();
      const version = data?.info?.version;
      if (typeof version !== "string" || !version.trim()) {
        throw new Error("Missing release version");
      }
      return version.trim();
    },
    staleTime: 60 * 60 * 1000,
    retry: 1,
  });

  return data;
}
