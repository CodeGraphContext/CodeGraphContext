package MyModule::Circle;
use strict;
use warnings;
use parent 'MyModule::Shapes';

sub area {
    my $self = shift;
    return 3.14 * ($self->{radius} ** 2);
}

1;
