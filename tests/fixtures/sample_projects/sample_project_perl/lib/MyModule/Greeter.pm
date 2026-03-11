package MyModule::Greeter;

use strict;
use warnings;

sub new {
    my ($class, %args) = @_;
    my $self = {
        greeting => $args{greeting} || "Hello",
    };
    return bless $self, $class;
}

sub greet {
    my ($self, $name) = @_;
    print $self->{greeting} . ", $name!\n";
}

1;
