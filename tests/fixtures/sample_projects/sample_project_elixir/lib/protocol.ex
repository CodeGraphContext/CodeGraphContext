defprotocol MyApp.Serializable do
  @doc "Serializes the given data"
  def serialize(data)
end

defimpl MyApp.Serializable, for: Map do
  def serialize(data), do: "Map: #{inspect(data)}"
end

defimpl MyApp.Serializable, for: List do
  def serialize(data), do: "List: #{inspect(data)}"
end
