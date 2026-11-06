Namespace Fx.Vb
    Public Module Util
        Public Function Twice(v As Integer) As Integer
            Return v * 2
        End Function

        Public Sub Go()
            Dim s = "🚀" : Twice(1)
            Dim b = Box.Make()
        End Sub
    End Module

    Public Class Box
        Public Sub New()
        End Sub

        Public Sub New(x As Integer)
        End Sub

        Public Shared Function Make() As Box
            Return New Box()
        End Function

        Public Sub Use()
            Dim e = "é" : Make()
        End Sub
    End Class
End Namespace
